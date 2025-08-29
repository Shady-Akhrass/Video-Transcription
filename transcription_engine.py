import os
import re
import speech_recognition as sr
import google.generativeai as genai
import whisper
from pydub import AudioSegment
from pydub.utils import make_chunks
from concurrent.futures import ThreadPoolExecutor, as_completed

class TranscriptionEngine:
    def __init__(self, progress_callback=None):
        self.progress_callback = progress_callback
        self.gemini_api_key = ""
        self.translate_var = False
        
    def set_gemini_api_key(self, api_key):
        self.gemini_api_key = api_key
        
    def set_translate_option(self, translate):
        self.translate_var = translate
        
    def format_timestamp(self, seconds):
        total_seconds = int(seconds)
        hours, remainder = divmod(total_seconds, 3600)
        minutes, secs = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    
    def translate_text(self, text, target_language="ar"):
        if not self.gemini_api_key or not text.strip():
            return ""
        
        try:
            genai.configure(api_key=self.gemini_api_key)
            model = genai.GenerativeModel('gemini-2.0-flash')
            
            if target_language == "ar":
                prompt = f"Translate the following English text to Arabic. Only return the translation, no explanations:\n\n{text}"
            else:
                prompt = f"Translate the following Arabic text to English. Only return the translation, no explanations:\n\n{text}"
                
            response = model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            print(f"Translation error: {e}")
            return f"[Translation Error: {str(e)}]"
    
    def process_transcription_text(self, text, timestamp):
        processed_text = text
        
        # Check for noise patterns
        background_noise_patterns = [
            r'\b(background|noise|static|silence|hum|buzz|interference)\b',
            r'\b(muffled|unclear|distant|faint)\s+(voice|speech|sound|audio)\b',
            r'\b(low|poor)\s+quality\b'
        ]
        
        for pattern in background_noise_patterns:
            if re.search(pattern, processed_text, re.IGNORECASE):
                processed_text = f"[inaudible {timestamp}] {processed_text}"
                break
        
        # Check for unclear segments
        unclear_patterns = [
            r'\b(unintelligible|incomprehensible|indiscernible)\b',
            r'\b(cannot|can\'t)\s+(understand|hear|make out)\b',
            r'\b(unclear|inaudible)\s+(speech|words|segment)\b'
        ]
        
        for pattern in unclear_patterns:
            if re.search(pattern, processed_text, re.IGNORECASE):
                processed_text = f"[unintelligible {timestamp}] {processed_text}"
                break
        
        # Process emphasis patterns
        words = processed_text.split()
        for i, word in enumerate(words):
            if word.isupper() and len(word) > 1:
                words[i] = f"**{word}**"
            elif word.startswith('!') and word.endswith('!'):
                words[i] = f"*{word}*"
        
        processed_text = ' '.join(words)
        processed_text = re.sub(r'(\b\w+\b)(\s+\1\b)+', r'**\1**', processed_text)
        processed_text = re.sub(r'\*(\w+)\*', r'*\1*', processed_text)
        processed_text = re.sub(r'_(\w+)_', r'*\1*', processed_text)
        processed_text = re.sub(r'\*\*(\w+)\*\*', r'**\1**', processed_text)
        
        return processed_text
    
    def transcribe_audio_segments(self, audio_path, segment_length_sec=15.0, is_transcribing=True):
        audio = AudioSegment.from_file(audio_path)

        if self.language == "ar-AR":
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

        chunk_length_ms = int(segment_length_sec * 1000)
        chunks = make_chunks(audio, chunk_length_ms)
        total_chunks = len(chunks)

        if self.progress_callback:
            self.progress_callback(f"Starting transcription... {total_chunks} segments")

        # Pre-export chunks to temporary files
        chunk_files = []
        for i, chunk in enumerate(chunks):
            if not is_transcribing:
                break
            timestamp_start = i * (chunk_length_ms // 1000)
            timestamp_str = self.format_timestamp(timestamp_start)
            chunk_filename = f"{audio_path}_chunk{i}.wav"
            chunk.export(chunk_filename, format="wav")
            chunk_files.append((i, chunk_filename, timestamp_str))

        if not is_transcribing:
            for _, path, _ in chunk_files:
                try:
                    os.remove(path)
                except Exception:
                    pass
            return []

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
                if self.translate_var and self.gemini_api_key:
                    arabic_text = self.translate_text(text)
                elif self.translate_var:
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
                if self.translate_var and self.gemini_api_key:
                    english_text = self.translate_text(text, "en")
                elif self.translate_var:
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

        transcription_data = []
        futures = []
        
        if self.language == "ar-AR":
            try:
                whisper_model = whisper.load_model("medium")
            except Exception as e:
                if self.progress_callback:
                    self.progress_callback(f"Failed to load Whisper model: {e}")
                for _, path, _ in chunk_files:
                    try:
                        os.remove(path)
                    except Exception:
                        pass
                return []
                
            max_workers = self.max_workers_arabic
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                for idx, path, ts in chunk_files:
                    if not is_transcribing:
                        break
                    futures.append(executor.submit(transcribe_arabic, idx, path, ts, whisper_model))
                
                completed = 0
                next_index = 0
                results_by_index = {}
                for future in as_completed(futures):
                    if not is_transcribing:
                        break
                    idx, ts, en_text, ar_text = future.result()
                    results_by_index[idx] = (ts, en_text, ar_text)
                    
                    while next_index in results_by_index:
                        ts_f, en_f, ar_f = results_by_index.pop(next_index)
                        segment_data = {'timestamp': ts_f, 'english': en_f, 'arabic': ar_f}
                        transcription_data.append(segment_data)
                        completed += 1
                        if self.progress_callback:
                            self.progress_callback(f"Segment {completed}/{total_chunks}")
                        next_index += 1
        else:
            max_workers = self.max_workers_english
            try:
                tmp_rec = sr.Recognizer()
                with sr.AudioFile(chunk_files[0][1]) as source0:
                    tmp_rec.adjust_for_ambient_noise(source0, duration=0.3)
                    baseline_energy = tmp_rec.energy_threshold
            except Exception:
                baseline_energy = 300
                
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                for idx, path, ts in chunk_files:
                    if not is_transcribing:
                        break
                    futures.append(executor.submit(transcribe_english, idx, path, ts, baseline_energy))
                
                completed = 0
                next_index = 0
                results_by_index = {}
                for future in as_completed(futures):
                    if not is_transcribing:
                        break
                    idx, ts, en_text, ar_text = future.result()
                    results_by_index[idx] = (ts, en_text, ar_text)
                    
                    while next_index in results_by_index:
                        ts_f, en_f, ar_f = results_by_index.pop(next_index)
                        segment_data = {'timestamp': ts_f, 'english': en_f, 'arabic': ar_f}
                        transcription_data.append(segment_data)
                        completed += 1
                        if self.progress_callback:
                            self.progress_callback(f"Segment {completed}/{total_chunks}")
                        next_index += 1

        # Cleanup remaining chunk files
        for _, path, _ in chunk_files:
            try:
                if os.path.exists(path):
                    os.remove(path)
            except Exception:
                pass

        return transcription_data
