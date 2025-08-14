import os
import sys
import re
import tempfile
import yt_dlp
import glob
import shutil
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import time
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from moviepy.video.io.VideoFileClip import VideoFileClip
from pydub import AudioSegment
from pydub.utils import make_chunks
import speech_recognition as sr
import google.generativeai as genai
import json
import whisper


class TranscriptionGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Video Transcription Tool with Translation")
        self.root.geometry("1200x800")
        
        self.current_audio_path = None
        self.transcription_data = []
        self.is_transcribing = False
        self.gemini_api_key = ""
        cpu_count = os.cpu_count() or 4
        self.max_workers_english = min(6, max(2, cpu_count))  
        self.max_workers_arabic = 1  
        self.language_var = tk.StringVar(value="en-US")  
        
        self.setup_ui()
        
    def setup_ui(self):
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(3, weight=1)
        
        # Input section
        input_frame = ttk.LabelFrame(main_frame, text="Input", padding="5")
        input_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), padx=5, pady=5)
        input_frame.columnconfigure(1, weight=1)
        
        ttk.Label(input_frame, text="Video/URL:").grid(row=0, column=0, sticky=tk.W, padx=5)
        self.input_var = tk.StringVar()
        self.input_entry = ttk.Entry(input_frame, textvariable=self.input_var, width=50)
        self.input_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5)
        
        ttk.Button(input_frame, text="Browse File", command=self.browse_file).grid(row=0, column=2, padx=5)
        
        # API Key section
        api_frame = ttk.LabelFrame(main_frame, text="Google Gemini API (Optional)", padding="5")
        api_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), padx=5, pady=5)
        api_frame.columnconfigure(1, weight=1)
        
        ttk.Label(api_frame, text="API Key:").grid(row=0, column=0, sticky=tk.W, padx=5)
        self.api_key_var = tk.StringVar()
        self.api_key_entry = ttk.Entry(api_frame, textvariable=self.api_key_var, show="*", width=50)
        self.api_key_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5)
        
        self.translate_var = tk.BooleanVar()
        
        # Language selection
        language_frame = ttk.Frame(api_frame)
        language_frame.grid(row=0, column=2, padx=5)
        
        ttk.Radiobutton(language_frame, text="English", variable=self.language_var, value="en-US").pack(side=tk.LEFT)
        ttk.Radiobutton(language_frame, text="Arabic", variable=self.language_var, value="ar-AR").pack(side=tk.LEFT)
        
        # Update UI based on language selection
        def update_language_ui(*args):
            pass
        
        self.language_var.trace('w', update_language_ui)
        
        self.translate_check = ttk.Checkbutton(api_frame, text="Translate to Arabic", variable=self.translate_var)
        self.translate_check.grid(row=0, column=3, padx=5)
        
        # Control buttons and segment length selector
        control_frame = ttk.Frame(main_frame)
        control_frame.grid(row=2, column=0, columnspan=2, pady=10)
        
        # Add segment length selector
        segment_frame = ttk.LabelFrame(control_frame, text="Segment Length (seconds)", padding="5")
        segment_frame.pack(side=tk.LEFT, padx=5)
        
        self.segment_length = tk.StringVar(value="15")  # Default 15 seconds
        segment_values = ["5", "10", "15", "20", "30", "45", "60"]
        self.segment_combo = ttk.Combobox(segment_frame, textvariable=self.segment_length, values=segment_values, width=5)
        self.segment_combo.pack(side=tk.LEFT, padx=5)
        
        self.start_button = ttk.Button(control_frame, text="Start Transcription", command=self.start_transcription)
        self.start_button.pack(side=tk.LEFT, padx=5)
        
        self.stop_button = ttk.Button(control_frame, text="Stop", command=self.stop_transcription, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=5)
        
        self.save_button = ttk.Button(control_frame, text="Save Results", command=self.save_results, state=tk.DISABLED)
        self.save_button.pack(side=tk.LEFT, padx=5)
        
        # Progress indicators
        progress_frame = ttk.Frame(control_frame)
        progress_frame.pack(side=tk.LEFT, padx=5)
        
        self.progress_var = tk.StringVar(value="Ready")
        self.progress_label = ttk.Label(progress_frame, textvariable=self.progress_var, justify=tk.LEFT)
        self.progress_label.pack(side=tk.TOP, padx=20, pady=2)
        
        # Progress bar in determinate mode
        self.progress_bar = ttk.Progressbar(progress_frame, length=300, mode='determinate')
        self.progress_bar.pack(side=tk.TOP, padx=5, pady=2)
        
        # Initialize progress bar
        self.progress_bar["value"] = 0
        self.progress_bar["maximum"] = 100
        
        # Results section
        results_frame = ttk.LabelFrame(main_frame, text="Transcription Results", padding="5")
        results_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)
        results_frame.columnconfigure(0, weight=1)
        results_frame.rowconfigure(0, weight=1)
        
        # Create Treeview for results
        self.tree = ttk.Treeview(results_frame, columns=('timestamp', 'english', 'arabic'), show='headings', height=15)
        self.tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure columns
        self.tree.heading('timestamp', text='Timestamp')
        self.tree.heading('english', text='English Text')
        self.tree.heading('arabic', text='Arabic Text')
        
        self.tree.column('timestamp', width=120, minwidth=100)
        self.tree.column('english', width=400, minwidth=300)
        self.tree.column('arabic', width=400, minwidth=300)
        
        # Scrollbars for treeview
        v_scrollbar = ttk.Scrollbar(results_frame, orient=tk.VERTICAL, command=self.tree.yview)
        v_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.tree.configure(yscrollcommand=v_scrollbar.set)
        
        h_scrollbar = ttk.Scrollbar(results_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        h_scrollbar.grid(row=1, column=0, sticky=(tk.W, tk.E))
        self.tree.configure(xscrollcommand=h_scrollbar.set)
        
        # Bind click event to tree
        self.tree.bind('<<TreeviewSelect>>', self.on_tree_select)
        
        # Current transcription display
        current_frame = ttk.LabelFrame(main_frame, text="Current Segment", padding="5")
        current_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E), padx=5, pady=5)
        current_frame.columnconfigure(0, weight=1)
        current_frame.columnconfigure(1, weight=1)
        
        # English text frame
        english_frame = ttk.LabelFrame(current_frame, text="English", padding="5")
        english_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5)
        english_frame.columnconfigure(0, weight=1)
        
        self.current_text = scrolledtext.ScrolledText(english_frame, height=4, wrap=tk.WORD)
        self.current_text.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=5, pady=5)
        
        # Bind keyboard shortcuts for English text
        self.current_text.bind('<Control-b>', self.toggle_bold_english)
        self.current_text.bind('<Control-B>', self.toggle_bold_english)
        self.current_text.bind('<Control-i>', self.toggle_italic_english)
        self.current_text.bind('<Control-I>', self.toggle_italic_english)
        self.current_text.bind('<Control-k>', self.insert_inaudible_timestamp_english)
        self.current_text.bind('<Control-K>', self.insert_inaudible_timestamp_english)
        self.current_text.bind('<Control-l>', self.insert_unintelligible_timestamp_english)
        self.current_text.bind('<Control-L>', self.insert_unintelligible_timestamp_english)
        
        # Arabic text frame
        arabic_frame = ttk.LabelFrame(current_frame, text="Arabic", padding="5")
        arabic_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5)
        arabic_frame.columnconfigure(0, weight=1)
        
        self.current_text_arabic = scrolledtext.ScrolledText(arabic_frame, height=4, wrap=tk.WORD)
        self.current_text_arabic.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=5, pady=5)
        
        # Bind keyboard shortcuts for Arabic text
        self.current_text_arabic.bind('<Control-b>', self.toggle_bold_arabic)
        self.current_text_arabic.bind('<Control-B>', self.toggle_bold_arabic)
        self.current_text_arabic.bind('<Control-i>', self.toggle_italic_arabic)
        self.current_text_arabic.bind('<Control-I>', self.toggle_italic_arabic)
        self.current_text_arabic.bind('<Control-k>', self.insert_inaudible_timestamp_arabic)
        self.current_text_arabic.bind('<Control-K>', self.insert_inaudible_timestamp_arabic)
        self.current_text_arabic.bind('<Control-l>', self.insert_unintelligible_timestamp_arabic)
        self.current_text_arabic.bind('<Control-L>', self.insert_unintelligible_timestamp_arabic)
        
    def browse_file(self):
        filename = filedialog.askopenfilename(
            title="Select Audio/Video File",
            filetypes=[
                ("All supported files", "*.mp4 *.avi *.mkv *.mov *.wmv *.flv *.webm *.mp3 *.wav *.aac *.ogg"),
                ("Video files", "*.mp4 *.avi *.mkv *.mov *.wmv *.flv *.webm"),
                ("Audio files", "*.mp3 *.wav *.aac *.ogg"),
                ("All files", "*.*")
            ]
        )
        if filename:
            self.input_var.set(filename)
    
    def is_youtube_url(self, url):
        return "youtube.com" in url or "youtu.be" in url
    
    def sanitize_filename(self, title):
        return re.sub(r'[\\/*?:"<>|：]', '_', title)
    
    def download_youtube_audio(self, url, output_path):
        try:
            # Create a temporary file for streaming
            temp_wav = os.path.join(output_path, "temp_streaming.wav")
            
            def my_hook(d):
                if d['status'] == 'downloading':
                    # Update progress
                    try:
                        progress = float(d['downloaded_bytes']) / float(d['total_bytes']) * 100
                        self.root.after(0, lambda: self.progress_var.set(
                            f"Downloading: {progress:.1f}%"
                        ))
                    except:
                        pass

            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': os.path.join(output_path, '%(title)s.%(ext)s'),
                'quiet': False,
                'progress_hooks': [my_hook],
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'wav',
                    'preferredquality': '192',
                }],
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                raw_title = info['title']
                sanitized_title = self.sanitize_filename(raw_title)

            # Find and process the downloaded file
            possible_files = glob.glob(os.path.join(output_path, "*.wav"))
            for f in possible_files:
                if os.path.exists(f):
                    new_path = os.path.join(output_path, sanitized_title + ".wav")
                    shutil.move(f, new_path)
                    
                    # Start processing in smaller chunks while file is being prepared
                    self.root.after(0, lambda: self.progress_var.set("Preparing audio for transcription..."))
                    
                    # Load audio in smaller chunks for faster processing
                    audio = AudioSegment.from_wav(new_path)
                    chunk_length = 30 * 1000  # 30 seconds chunks for initial loading
                    chunks = make_chunks(audio, chunk_length)
                    
                    # Pre-process first chunk immediately
                    if chunks:
                        first_chunk = chunks[0]
                        first_chunk = first_chunk.set_channels(1).set_frame_rate(16000)
                        first_chunk.export(temp_wav, format="wav")
                    
                    return new_path, sanitized_title

            return None, None

        except Exception as e:
            messagebox.showerror("Error", f"Failed to download YouTube video: {e}")
            return None, None

    def extract_audio_from_local(self, input_path, output_path):
        try:
            title = os.path.splitext(os.path.basename(input_path))[0]
            audio_file = os.path.join(output_path, f"{title}.wav")
            
            # Check if input is already an audio file
            audio_extensions = ['.mp3', '.wav', '.aac', '.ogg']
            if os.path.splitext(input_path)[1].lower() in audio_extensions:
                # Convert audio file to WAV using pydub with enhanced settings
                audio = AudioSegment.from_file(input_path)
                # Special processing for Arabic audio
                if self.language_var.get() == "ar-AR":
                    # Apply specific processing for Arabic speech
                    audio = audio.set_channels(1)  # Mono
                    audio = audio.set_frame_rate(16000)  # 16kHz sample rate
                    audio = audio.low_pass_filter(4000)  # Emphasize speech frequencies
                    audio = audio.high_pass_filter(300)  # Reduce low-frequency noise
                else:
                    # Standard processing for English
                    audio = audio.set_channels(1)
                    audio = audio.set_frame_rate(16000)
                
                audio = audio.normalize()  # Normalize volume
                audio.export(audio_file, format='wav', parameters=["-ar", "16000", "-ac", "1"])
            else:
                # Extract audio from video safely using context manager
                with VideoFileClip(input_path) as clip:
                    audio = clip.audio
                    # Convert to WAV with enhanced settings
                    audio.write_audiofile(audio_file, fps=16000, nbytes=2, logger=None)
            
            return audio_file, title
        except Exception as e:
            messagebox.showerror("Error", f"Failed to extract/convert audio: {e}")
            return None, None
    
    def format_timestamp(self, seconds):
        total_seconds = int(seconds)
        hours, remainder = divmod(total_seconds, 3600)
        minutes, secs = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    
    def translate_text(self, text):
        if not self.gemini_api_key or not text.strip():
            return ""
        
        try:
            genai.configure(api_key=self.gemini_api_key)
            model = genai.GenerativeModel('gemini-2.0-flash')
            
            prompt = f"Translate the following English text to Arabic. Only return the translation, no explanations:\n\n{text}"
            response = model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            print(f"Translation error: {e}")
            return f"[Translation Error: {str(e)}]"
    
    def transcribe_audio_segments(self, audio_path):
        """Transcribe audio in parallel where safe. English uses thread pool; Arabic (Whisper) stays single-threaded by default."""
        # Load and enhance audio once
        audio = AudioSegment.from_file(audio_path)

        if self.language_var.get() == "ar-AR":
            audio = (
                audio.set_channels(1)
                     .set_frame_rate(16000)
                     .normalize()
                     .low_pass_filter(8000)
                     .high_pass_filter(100)
            )
        else:
            audio = (
                audio.low_pass_filter(3500)
                     .high_pass_filter(300)
                     .normalize()
                     .set_channels(1)
                     .set_frame_rate(16000)
            )

        try:
            segment_length_sec = float(self.segment_length.get())
        except ValueError:
            segment_length_sec = 15.0
        chunk_length_ms = int(segment_length_sec * 1000)

        chunks = make_chunks(audio, chunk_length_ms)
        total_chunks = len(chunks)
        total_duration = len(audio) / 1000.0

        self.progress_bar["maximum"] = total_chunks
        self.progress_bar["value"] = 0
        self.transcription_data = []

        self.root.after(0, lambda: self.progress_var.set(
            f"Starting transcription...\n"
            f"Segment length: {segment_length_sec:.1f} seconds\n"
            f"Total segments: {total_chunks}\n"
            f"Total duration: {total_duration:.1f} seconds"
        ))

        # Pre-export chunks to temporary files and collect metadata
        chunk_files = []
        for i, chunk in enumerate(chunks):
            if not self.is_transcribing:
                break
            timestamp_start = i * (chunk_length_ms // 1000)
            timestamp_str = self.format_timestamp(timestamp_start)
            chunk_filename = f"{audio_path}_chunk{i}.wav"
            chunk.export(chunk_filename, format="wav")
            chunk_files.append((i, chunk_filename, timestamp_str))

        if not self.is_transcribing:
            # Cleanup exported chunks if stopped
            for _, path, _ in chunk_files:
                try:
                    os.remove(path)
                except Exception:
                    pass
            return

        # Helper functions per language
        def transcribe_english(index, chunk_path, timestamp_str, baseline_energy):
            recognizer = sr.Recognizer()
            recognizer.energy_threshold = baseline_energy
            recognizer.dynamic_energy_threshold = True
            recognizer.dynamic_energy_adjustment_damping = 0.15
            recognizer.dynamic_energy_ratio = 1.5

            english_text = ""
            arabic_text = ""
            try:
                with sr.AudioFile(chunk_path) as source:
                    audio_data = recognizer.record(source)
                text = recognizer.recognize_google(audio_data, language="en-US")
                text = self.process_transcription_text(text, timestamp_str)
                english_text = text
                if self.translate_var.get():
                    if self.api_key_var.get().strip():
                        arabic_text = self.translate_text(text)
                    else:
                        arabic_text = "[API key needed for translation]"
            except sr.UnknownValueError:
                english_text = "[No speech detected]"
            except sr.RequestError as e:
                english_text = f"[API Error: {e}]"
            finally:
                try:
                    os.remove(chunk_path)
                except Exception:
                    pass
            return index, timestamp_str, english_text, arabic_text

        def transcribe_arabic(index, chunk_path, timestamp_str, whisper_model):
            english_text = ""
            arabic_text = ""
            try:
                result = whisper_model.transcribe(
                    chunk_path,
                    language="ar",
                    task="transcribe",
                    initial_prompt=(
                        "Transcribe in Modern Standard Arabic. If this is a conversation, "
                        "format each speaker's line with a dash (-) at the beginning. "
                        "If there's a clear speaker identification, include it with a colon."
                    ),
                )
                text = result.get("text", "").strip()
                text = self.process_transcription_text(text, timestamp_str)
                if text.count("-") > 1 or ":" in text:
                    arabic_text = text
                else:
                    arabic_text = f"- {text}" if text and not text.startswith("-") else text
                if self.translate_var.get():
                    if self.api_key_var.get().strip():
                        english_text = self.translate_text(text)
                    else:
                        english_text = "[API key needed for translation]"
            except Exception as e:
                print(f"Whisper transcription error: {e}")
                arabic_text = "[خطأ في التعرف على الكلام]"
            finally:
                try:
                    os.remove(chunk_path)
                except Exception:
                    pass
            return index, timestamp_str, english_text, arabic_text

        futures = []
        if self.language_var.get() == "ar-AR":
            try:
                whisper_model = whisper.load_model("medium")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load Whisper model: {e}")
                # Cleanup chunks
                for _, path, _ in chunk_files:
                    try:
                        os.remove(path)
                    except Exception:
                        pass
                return
            max_workers = self.max_workers_arabic
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                for idx, path, ts in chunk_files:
                    if not self.is_transcribing:
                        break
                    futures.append(executor.submit(transcribe_arabic, idx, path, ts, whisper_model))
                # Ensure ordered emission by index
                completed = 0
                next_index = 0
                results_by_index = {}
                for future in as_completed(futures):
                    if not self.is_transcribing:
                        break
                    idx, ts, en_text, ar_text = future.result()
                    results_by_index[idx] = (ts, en_text, ar_text)
                    # Flush in order
                    while next_index in results_by_index:
                        ts_f, en_f, ar_f = results_by_index.pop(next_index)
                        segment_data = {'timestamp': ts_f, 'english': en_f, 'arabic': ar_f}
                        self.transcription_data.append(segment_data)
                        completed += 1
                        self._update_progress_ui(completed, total_chunks, next_index, chunk_length_ms)
                        self.root.after(0, lambda data=segment_data: (
                            self.add_to_tree(data),
                            self.update_current_display(en_f, ar_f),
                            self.tree.see(self.tree.get_children()[-1]) if self.tree.get_children() else None
                        ))
                        next_index += 1
        else:
            max_workers = self.max_workers_english
            # Compute ambient noise baseline once using first chunk
            try:
                tmp_rec = sr.Recognizer()
                with sr.AudioFile(chunk_files[0][1]) as source0:
                    tmp_rec.adjust_for_ambient_noise(source0, duration=0.3)
                    baseline_energy = tmp_rec.energy_threshold
            except Exception:
                baseline_energy = 300
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                for idx, path, ts in chunk_files:
                    if not self.is_transcribing:
                        break
                    futures.append(executor.submit(transcribe_english, idx, path, ts, baseline_energy))
                # Ensure ordered emission
                completed = 0
                next_index = 0
                results_by_index = {}
                for future in as_completed(futures):
                    if not self.is_transcribing:
                        break
                    idx, ts, en_text, ar_text = future.result()
                    results_by_index[idx] = (ts, en_text, ar_text)
                    while next_index in results_by_index:
                        ts_f, en_f, ar_f = results_by_index.pop(next_index)
                        segment_data = {'timestamp': ts_f, 'english': en_f, 'arabic': ar_f}
                        self.transcription_data.append(segment_data)
                        completed += 1
                        self._update_progress_ui(completed, total_chunks, next_index, chunk_length_ms)
                        self.root.after(0, lambda data=segment_data: (
                            self.add_to_tree(data),
                            self.update_current_display(en_f, ar_f),
                            self.tree.see(self.tree.get_children()[-1]) if self.tree.get_children() else None
                        ))
                        next_index += 1

        # Final cleanup: remove any remaining chunk files if they still exist
        for _, path, _ in chunk_files:
            try:
                if os.path.exists(path):
                    os.remove(path)
            except Exception:
                pass

    def _update_progress_ui(self, completed, total_chunks, idx, chunk_length_ms):
        current_time = completed * (chunk_length_ms // 1000)
        total_time = total_chunks * (chunk_length_ms // 1000)
        segment_start = idx * (chunk_length_ms // 1000)
        segment_end = (idx + 1) * (chunk_length_ms // 1000)
        status_text = (
            f"Segment {completed}/{total_chunks}\n"
            f"Current segment: {segment_start}-{segment_end} seconds\n"
            f"Progress: {(completed/total_chunks)*100:.1f}%\n"
            f"Total progress: {current_time}s / {total_time}s"
        )
        self.root.after(0, lambda: self.progress_var.set(status_text))
        self.root.after(0, lambda: setattr(self.progress_bar, "value", completed))
    
    def process_audio_stream(self, audio_path):
        """Process audio in a streaming fashion while it's being downloaded/prepared"""
        try:
            chunk_size = 5 * 1000  # 5 second chunks
            audio = AudioSegment.from_wav(audio_path)
            
            # Process audio in small chunks
            chunks = make_chunks(audio, chunk_size)
            for i, chunk in enumerate(chunks):
                if not self.is_transcribing:
                    break
                    
                # Process chunk
                processed_chunk = chunk.set_channels(1).set_frame_rate(16000)
                if self.language_var.get() == "ar-AR":
                    processed_chunk = (processed_chunk
                        .low_pass_filter(4000)
                        .high_pass_filter(250)
                        .compress_dynamic_range())
                else:
                    processed_chunk = (processed_chunk
                        .low_pass_filter(3500)
                        .high_pass_filter(300))
                
                # Save processed chunk
                chunk_path = f"{audio_path}_chunk_{i}.wav"
                processed_chunk.export(chunk_path, format="wav")
                
        except Exception as e:
            print(f"Error in audio stream processing: {e}")
            
    def update_current_display(self, english_text, arabic_text=""):
        self.current_text.delete(1.0, tk.END)
        self.current_text_arabic.delete(1.0, tk.END)
        
        # If in Arabic mode, prioritize showing Arabic text
        if self.language_var.get() == "ar-AR":
            # Show Arabic text always
            self.current_text_arabic.insert(1.0, arabic_text)
            # Only show English if translation was requested
            if self.translate_var.get():
                self.current_text.insert(1.0, english_text)
        else:
            # In English mode
            self.current_text.insert(1.0, english_text)
            # Only show Arabic if translation was requested
            if self.translate_var.get():
                self.current_text_arabic.insert(1.0, arabic_text)
    
    def on_tree_select(self, event):
        selected_items = self.tree.selection()
        if selected_items:
            # Get values of the selected row
            item = selected_items[0]
            values = self.tree.item(item)['values']
            if values:
                # values[1] is English text, values[2] is Arabic text
                self.update_current_display(values[1], values[2])
    
    def add_to_tree(self, data):
        self.tree.insert('', tk.END, values=(data['timestamp'], data['english'], data['arabic']))
        # Auto-scroll to the latest entry
        items = self.tree.get_children()
        if items:
            self.tree.see(items[-1])
    
    def start_transcription(self):
        input_path = self.input_var.get().strip()
        if not input_path:
            messagebox.showerror("Error", "Please provide a video file or YouTube URL")
            return
        
        # Set API key if provided
        self.gemini_api_key = self.api_key_var.get().strip()
        
        # Clear previous results
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.transcription_data = []
        self.current_text.delete(1.0, tk.END)
        
        # Update UI state
        self.is_transcribing = True
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.save_button.config(state=tk.DISABLED)
        self.progress_bar["value"] = 0
        self.progress_var.set("Preparing...")
        
        # Start transcription in a separate thread
        thread = threading.Thread(target=self.transcription_worker, args=(input_path,))
        thread.daemon = True
        thread.start()
    
    def transcription_worker(self, input_path):
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                is_youtube = self.is_youtube_url(input_path)
                
                if is_youtube:
                    self.root.after(0, lambda: self.progress_var.set("Downloading YouTube audio..."))
                    audio_path, title = self.download_youtube_audio(input_path, tmpdir)
                else:
                    self.root.after(0, lambda: self.progress_var.set("Extracting audio..."))
                    audio_path, title = self.extract_audio_from_local(input_path, tmpdir)
                
                if not audio_path or not self.is_transcribing:
                    return
                
                # Start transcription
                self.root.after(0, lambda: self.progress_var.set("Starting transcription..."))
                self.transcribe_audio_segments(audio_path)
                
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Transcription failed: {e}"))
        finally:
            self.root.after(0, self.transcription_finished)
    
    def transcription_finished(self):
        self.is_transcribing = False
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.save_button.config(state=tk.NORMAL)
        self.progress_bar["value"] = self.progress_bar["maximum"]
        self.progress_var.set("Transcription completed")
        
        if self.transcription_data:
            messagebox.showinfo("Success", f"Transcription completed! {len(self.transcription_data)} segments processed.")
    
    def stop_transcription(self):
        self.is_transcribing = False
        self.progress_var.set("Stopping...")
    
    def process_transcription_text(self, text, timestamp):
        """Automatically process and format transcription text"""
        # Define noise patterns to detect
        background_noise_patterns = [
            r'\b(background|noise|static|silence|hum|buzz|interference)\b',
            r'\b(muffled|unclear|distant|faint)\s+(voice|speech|sound|audio)\b',
            r'\b(low|poor)\s+quality\b'
        ]
        
        # Initialize processed text
        processed_text = text
        
        # Check for segments that might need [inaudible] tag
        for pattern in background_noise_patterns:
            if re.search(pattern, processed_text, re.IGNORECASE):
                processed_text = f"[inaudible {timestamp}] {processed_text}"
                break
        
        # Check for unclear or unintelligible segments
        unclear_patterns = [
            r'\b(unintelligible|incomprehensible|indiscernible)\b',
            r'\b(cannot|can\'t)\s+(understand|hear|make out)\b',
            r'\b(unclear|inaudible)\s+(speech|words|segment)\b'
        ]
        
        for pattern in unclear_patterns:
            if re.search(pattern, processed_text, re.IGNORECASE):
                processed_text = f"[unintelligible {timestamp}] {processed_text}"
                break
        
        # Process emphasis patterns (for bold and italic)
        # Look for words in ALL CAPS or with surrounding punctuation that might indicate emphasis
        words = processed_text.split()
        for i, word in enumerate(words):
            # Check for emphasized words (ALL CAPS)
            if word.isupper() and len(word) > 1:
                words[i] = f"**{word}**"  # Make it bold
            # Check for words with special punctuation that might indicate emphasis
            elif word.startswith('!') and word.endswith('!'):
                words[i] = f"*{word}*"  # Make it italic
        
        processed_text = ' '.join(words)
        
        # Look for repeated words or sounds that might indicate emphasis
        processed_text = re.sub(r'(\b\w+\b)(\s+\1\b)+', r'**\1**', processed_text)
        
        # Look for words between asterisks or underscores and format them
        processed_text = re.sub(r'\*(\w+)\*', r'*\1*', processed_text)  # Italic
        processed_text = re.sub(r'_(\w+)_', r'*\1*', processed_text)    # Italic
        processed_text = re.sub(r'\*\*(\w+)\*\*', r'**\1**', processed_text)  # Bold
        
        return processed_text
        
    def get_current_timestamp(self):
        """Get timestamp from currently selected segment"""
        selected_items = self.tree.selection()
        if selected_items:
            item = selected_items[0]
            values = self.tree.item(item)['values']
            if values:
                return values[0]  # timestamp is the first value
        return "00:00:00"
        
    def format_text(self, widget, format_type):
        try:
            selected_text = widget.get(tk.SEL_FIRST, tk.SEL_END)
            if selected_text:
                if format_type == "bold":
                    formatted_text = f"**{selected_text}**"
                elif format_type == "italic":
                    formatted_text = f"*{selected_text}*"
                widget.delete(tk.SEL_FIRST, tk.SEL_END)
                widget.insert(tk.INSERT, formatted_text)
        except tk.TclError:
            pass  # No selection
            
    def insert_timestamp_text(self, widget, timestamp_type):
        timestamp = self.get_current_timestamp()
        if timestamp_type == "inaudible":
            text = f"[inaudible {timestamp}]"
        else:
            text = f"[unintelligible {timestamp}]"
        widget.insert(tk.INSERT, text)
            
    def toggle_bold_english(self, event):
        self.format_text(self.current_text, "bold")
        return "break"
        
    def toggle_italic_english(self, event):
        self.format_text(self.current_text, "italic")
        return "break"
        
    def insert_inaudible_timestamp_english(self, event):
        self.insert_timestamp_text(self.current_text, "inaudible")
        return "break"
        
    def insert_unintelligible_timestamp_english(self, event):
        self.insert_timestamp_text(self.current_text, "unintelligible")
        return "break"
        
    def toggle_bold_arabic(self, event):
        self.format_text(self.current_text_arabic, "bold")
        return "break"
        
    def toggle_italic_arabic(self, event):
        self.format_text(self.current_text_arabic, "italic")
        return "break"
        
    def insert_inaudible_timestamp_arabic(self, event):
        timestamp = self.get_current_timestamp()
        self.insert_timestamp_text(self.current_text_arabic, "inaudible")
        return "break"
        
    def insert_unintelligible_timestamp_arabic(self, event):
        timestamp = self.get_current_timestamp()
        self.insert_timestamp_text(self.current_text_arabic, "unintelligible")
        return "break"
    
    def save_results(self):
        if not self.transcription_data:
            messagebox.showwarning("Warning", "No transcription data to save")
            return
        
        # Ask for save location
        base_filename = filedialog.asksaveasfilename(
            title="Save Transcription Results",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if not base_filename:
            return
        
        try:
            base_name = os.path.splitext(base_filename)[0]
            
            # Save timestamps and English text
            with open(f"{base_name}_timestamps.txt", "w", encoding="utf-8") as f:
                for segment in self.transcription_data:
                    f.write(f"{segment['timestamp']}: {segment['english']}\n")
            
            # Save English text only
            with open(f"{base_name}_english.txt", "w", encoding="utf-8") as f:
                for segment in self.transcription_data:
                    if segment['english'] and not segment['english'].startswith('['):
                        f.write(f"{segment['english']} ")
            
            # Save Arabic translation if available with Gemini AI correction
            if any(segment['arabic'] for segment in self.transcription_data):
                # Collect all Arabic text for batch correction
                arabic_text = " ".join([
                    segment['arabic'] 
                    for segment in self.transcription_data 
                    if segment['arabic'] and not segment['arabic'].startswith('[')
                ])
                
                # Use Gemini AI to correct the Arabic text
                try:
                    if self.gemini_api_key and arabic_text.strip():
                        genai.configure(api_key=self.gemini_api_key)
                        model = genai.GenerativeModel('gemini-2.0-flash')
                        
                        prompt = (
                            "قم بتصحيح الأخطاء الإملائية والنحوية فقط في النص التالي مع الحفاظ على نفس الكلمات والمعنى. "
                            "قد يكون هذا حواراً بين عدة متحدثين. "
                            "قواعد مهمة:\n"
                            "1. حافظ على علامات المتحدثين (الأسطر التي تبدأ بـ '-' أو تحتوي على ':')\n"
                            "2. حافظ على فواصل الأسطر بين المتحدثين\n"
                            "3. حافظ على أسماء المتحدثين إن وجدت (قبل علامة :)\n"
                            "4. صحح الأخطاء النحوية والإملائية فقط دون تغيير الكلمات\n"
                            "5. حافظ على نفس المصطلحات والكلمات المستخدمة حتى لو كانت عامية\n\n"
                            "النص المراد تصحيحه:\n"
                            f"{arabic_text}"
                        )
                        
                        response = model.generate_content(prompt)
                        corrected_arabic = response.text.strip()
                    else:
                        corrected_arabic = arabic_text
                        
                    # Save the corrected Arabic text with proper conversation formatting
                    with open(f"{base_name}_arabic.txt", "w", encoding="utf-8") as f:
                        # Add a header for the transcript
                        f.write("المحادثة:\n")
                        f.write("=" * 40 + "\n\n")
                        
                        # Write the corrected text with proper line spacing for conversations
                        lines = corrected_arabic.split('\n')
                        for line in lines:
                            if line.strip():
                                # Add extra spacing for new speakers
                                if line.strip().startswith('-') or ':' in line:
                                    f.write('\n')
                                f.write(line + '\n')
                        
                    # Update the transcription data with corrected text
                    if self.gemini_api_key:
                        # Split by conversation turns instead of word count
                        corrected_lines = corrected_arabic.split('\n')
                        valid_segments = [s for s in self.transcription_data if s['arabic'] and not s['arabic'].startswith('[')]
                        
                        # Try to match corrected lines with segments based on content similarity
                        current_line = 0
                        for segment in valid_segments:
                            if current_line < len(corrected_lines):
                                segment['arabic'] = corrected_lines[current_line].strip()
                                current_line += 1
                        
                        for segment in self.transcription_data:
                            if segment['arabic'] and not segment['arabic'].startswith('['):
                                segment['arabic'] = corrected_lines[current_line].strip()
                                current_line += 1
                                
                except Exception as e:
                    print(f"Arabic correction error: {e}")
                    # Fallback to original text if correction fails
                    with open(f"{base_name}_arabic.txt", "w", encoding="utf-8") as f:
                        for segment in self.transcription_data:
                            if segment['arabic'] and not segment['arabic'].startswith('['):
                                f.write(f"{segment['arabic']} ")
            
            # Save complete data as JSON
            with open(f"{base_name}_complete.json", "w", encoding="utf-8") as f:
                json.dump(self.transcription_data, f, ensure_ascii=False, indent=2)
            
            messagebox.showinfo("Success", f"Results saved to:\n"
                                         f"• {base_name}_timestamps.txt\n"
                                         f"• {base_name}_english.txt\n" +
                                         (f"• {base_name}_arabic.txt\n" if any(s['arabic'] for s in self.transcription_data) else "") +
                                         f"• {base_name}_complete.json")
        
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save results: {e}")


def main():
    root = tk.Tk()
    app = TranscriptionGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()