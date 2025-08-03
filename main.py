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
from concurrent.futures import ThreadPoolExecutor
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
        self.gemini_api_key = "AIzaSyB28oyoC-uDn8ijlQQb6vIcC0A-lL1LpSE"
        self.language_var = tk.StringVar(value="en-US")  # Default language
        
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
        
        # Arabic dialects frame
        self.dialects_frame = ttk.LabelFrame(api_frame, text="Arabic Dialects", padding="5")
        self.dialects_frame.grid(row=1, column=0, columnspan=4, sticky=(tk.W, tk.E), padx=5, pady=5)
        
        # Arabic dialect checkboxes
        self.dialect_vars = {
            'ar-SA': tk.BooleanVar(value=True),  # Saudi Arabic
            'ar-EG': tk.BooleanVar(value=True),  # Egyptian Arabic
            'ar-AE': tk.BooleanVar(value=True),  # UAE Arabic
            'ar-KW': tk.BooleanVar(value=False), # Kuwaiti Arabic
            'ar-MA': tk.BooleanVar(value=False), # Moroccan Arabic
            'ar-TN': tk.BooleanVar(value=False), # Tunisian Arabic
            'ar-OM': tk.BooleanVar(value=False), # Omani Arabic
            'ar-QA': tk.BooleanVar(value=False), # Qatari Arabic
            'ar-BH': tk.BooleanVar(value=False)  # Bahraini Arabic
        }
        
        # Create checkboxes in a grid layout
        dialect_labels = {
            'ar-SA': 'Saudi',
            'ar-EG': 'Egyptian',
            'ar-AE': 'UAE',
            'ar-KW': 'Kuwaiti',
            'ar-MA': 'Moroccan',
            'ar-TN': 'Tunisian',
            'ar-OM': 'Omani',
            'ar-QA': 'Qatari',
            'ar-BH': 'Bahraini'
        }
        
        for i, (dialect, var) in enumerate(self.dialect_vars.items()):
            row = i // 3
            col = i % 3
            ttk.Checkbutton(
                self.dialects_frame,
                text=dialect_labels[dialect],
                variable=var
            ).grid(row=row, column=col, padx=5, pady=2, sticky=tk.W)
        
        # Update dialects visibility based on language selection
        def update_dialects_visibility(*args):
            if self.language_var.get() == "ar-AR":
                self.dialects_frame.grid()
            else:
                self.dialects_frame.grid_remove()
        
        self.language_var.trace('w', update_dialects_visibility)
        update_dialects_visibility()  # Initial state
        
        self.translate_check = ttk.Checkbutton(api_frame, text="Translate to Arabic", variable=self.translate_var)
        self.translate_check.grid(row=0, column=3, padx=5)
        
        # Control buttons
        control_frame = ttk.Frame(main_frame)
        control_frame.grid(row=2, column=0, columnspan=2, pady=10)
        
        self.start_button = ttk.Button(control_frame, text="Start Transcription", command=self.start_transcription)
        self.start_button.pack(side=tk.LEFT, padx=5)
        
        self.stop_button = ttk.Button(control_frame, text="Stop", command=self.stop_transcription, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=5)
        
        self.save_button = ttk.Button(control_frame, text="Save Results", command=self.save_results, state=tk.DISABLED)
        self.save_button.pack(side=tk.LEFT, padx=5)
        
        # Progress bar
        self.progress_var = tk.StringVar(value="Ready")
        self.progress_label = ttk.Label(control_frame, textvariable=self.progress_var)
        self.progress_label.pack(side=tk.LEFT, padx=20)
        
        self.progress_bar = ttk.Progressbar(control_frame, length=200, mode='indeterminate')
        self.progress_bar.pack(side=tk.LEFT, padx=5)
        
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
        
        # Arabic text frame
        arabic_frame = ttk.LabelFrame(current_frame, text="Arabic", padding="5")
        arabic_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5)
        arabic_frame.columnconfigure(0, weight=1)
        
        self.current_text_arabic = scrolledtext.ScrolledText(arabic_frame, height=4, wrap=tk.WORD)
        self.current_text_arabic.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=5, pady=5)
        
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
                # Extract audio from video
                clip = VideoFileClip(input_path)
                audio = clip.audio
                clip.close()
                # Convert to WAV with enhanced settings
                audio.write_audiofile(audio_file, fps=16000, nbytes=2, logger=None)
            
            return audio_file, title
        except Exception as e:
            messagebox.showerror("Error", f"Failed to extract/convert audio: {e}")
            return None, None
    
    def format_timestamp(self, seconds):
        td = timedelta(seconds=seconds)
        hours, remainder = divmod(td.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    
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
        recognizer = sr.Recognizer()
        
        # Initialize Whisper model for Arabic
        if self.language_var.get() == "ar-AR":
            try:
                whisper_model = whisper.load_model("medium")  # You can use "base", "small", or "large" depending on your needs
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load Whisper model: {e}")
                return
        else:
            # Standard settings for English
            recognizer.energy_threshold = 300
            recognizer.dynamic_energy_threshold = True
            recognizer.dynamic_energy_adjustment_damping = 0.15
            recognizer.dynamic_energy_ratio = 1.5

        # Load and enhance audio
        audio = AudioSegment.from_file(audio_path)

        # Apply enhanced audio processing for better recognition
        if self.language_var.get() == "ar-AR":
            # Arabic-specific processing for Whisper
            audio = audio.set_channels(1)  # Convert to mono
            audio = audio.set_frame_rate(16000)  # Set optimal sample rate
            audio = audio.normalize()  # Normalize volume
        else:
            # English processing
            audio = audio.low_pass_filter(3500)
            audio = audio.high_pass_filter(300)
            audio = audio.normalize()
            audio = audio.set_channels(1)
            audio = audio.set_frame_rate(16000)
            
        # Set chunk length (longer for Arabic with Whisper)
        chunk_length_ms = 30000 if self.language_var.get() == "ar-AR" else 5000  # 30 seconds for Arabic, 5 seconds for English
        
        chunks = make_chunks(audio, chunk_length_ms)
        total_chunks = len(chunks)
        self.transcription_data = []

        for i, chunk in enumerate(chunks):
            if not self.is_transcribing:
                break

            # Update progress
            self.root.after(0, lambda i=i: self.progress_var.set(f"Processing segment {i+1}/{total_chunks}"))

            timestamp_start = i * (chunk_length_ms // 1000)
            timestamp_str = self.format_timestamp(timestamp_start)

            chunk_filename = f"{audio_path}_chunk{i}.wav"
            chunk.export(chunk_filename, format="wav")

            english_text = ""
            arabic_text = ""

            try:
                if self.language_var.get() == "ar-AR":
                    # Use Whisper for Arabic transcription
                    try:
                        result = whisper_model.transcribe(
                            chunk_filename,
                            language="ar",
                            task="transcribe"
                        )
                        text = result["text"].strip()
                        arabic_text = text

                        # Translate to English if requested
                        if self.translate_var.get() and self.api_key_var.get().strip():
                            english_text = self.translate_text(text)
                        else:
                            english_text = ""

                    except Exception as e:
                        print(f"Whisper transcription error: {e}")
                        arabic_text = "[خطأ في التعرف على الكلام]"
                        english_text = ""
                else:
                    # Use existing speech recognition for English
                    with sr.AudioFile(chunk_filename) as source:
                        recognizer.adjust_for_ambient_noise(source, duration=0.5)
                        audio_data = recognizer.record(source)
                        
                        try:
                            text = recognizer.recognize_google(audio_data, language="en-US")
                            english_text = text
                            
                            # Translate to Arabic if requested
                            if self.translate_var.get() and self.api_key_var.get().strip():
                                arabic_text = self.translate_text(text)
                            else:
                                arabic_text = ""
                        except sr.UnknownValueError:
                            english_text = "[No speech detected]"
                            arabic_text = ""
                        except sr.RequestError as e:
                            english_text = f"[API Error: {e}]"
                            arabic_text = ""

                    except sr.UnknownValueError:
                        if self.language_var.get() == "ar-AR":
                            arabic_text = "[لم يتم التعرف على الكلام]"
                        else:
                            english_text = "[No speech detected]"
                    except sr.RequestError as e:
                        if self.language_var.get() == "ar-AR":
                            arabic_text = f"[خطأ في الخدمة: {e}]"
                        else:
                            english_text = f"[API Error: {e}]"
            finally:
                if os.path.exists(chunk_filename):
                    try:
                        os.remove(chunk_filename)
                    except PermissionError:
                        pass

            # Store segment data
            segment_data = {
                'timestamp': timestamp_str,
                'english': english_text,
                'arabic': arabic_text
            }
            self.transcription_data.append(segment_data)

            # Update tree view and current display immediately
            self.root.after(0, lambda data=segment_data: (
                self.add_to_tree(data),
                self.update_current_display(english_text, arabic_text),
                self.tree.see(self.tree.get_children()[-1]) if self.tree.get_children() else None
            ))

            # Update progress with time information
            current_time = (i + 1) * (chunk_length_ms // 1000)
            total_time = total_chunks * (chunk_length_ms // 1000)
            self.root.after(0, lambda: self.progress_var.set(
                f"Processing {current_time}s / {total_time}s ({i+1}/{total_chunks} chunks)"
            ))

            # Brief delay for UI responsiveness
            time.sleep(0.05)
    
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
        self.current_text.insert(1.0, english_text)
        self.current_text_arabic.delete(1.0, tk.END)
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
        self.progress_bar.start()
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
                
                # Process audio in streaming fashion
                self.root.after(0, lambda: self.progress_var.set("Starting transcription..."))
                
                # Create a thread pool for parallel processing
                with ThreadPoolExecutor(max_workers=2) as executor:
                    # Submit audio processing task
                    audio_future = executor.submit(self.process_audio_stream, audio_path)
                    
                    # Start transcription immediately while audio is being processed
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
        self.progress_bar.stop()
        self.progress_var.set("Transcription completed")
        
        if self.transcription_data:
            messagebox.showinfo("Success", f"Transcription completed! {len(self.transcription_data)} segments processed.")
    
    def stop_transcription(self):
        self.is_transcribing = False
        self.progress_var.set("Stopping...")
    
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
            
            # Save Arabic translation if available
            if any(segment['arabic'] for segment in self.transcription_data):
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