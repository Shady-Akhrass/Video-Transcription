import os
import re
import tempfile
import yt_dlp
import glob
import shutil
from moviepy.video.io.VideoFileClip import VideoFileClip
from pydub import AudioSegment
from pydub.utils import make_chunks

class AudioProcessor:
    def __init__(self, progress_callback=None):
        self.progress_callback = progress_callback
    
    def is_youtube_url(self, url):
        """Check if the given URL is a YouTube URL"""
        return "youtube.com" in url or "youtu.be" in url
    
    def sanitize_filename(self, title):
        """Sanitize filename by removing invalid characters"""
        return re.sub(r'[\\/*?:"<>|：]', '_', title)
    
    def download_youtube_audio(self, url, output_path):
        """Download audio from YouTube URL"""
        try:
            # Create a temporary file for streaming
            temp_wav = os.path.join(output_path, "temp_streaming.wav")
            
            def my_hook(d):
                if d['status'] == 'downloading':
                    # Update progress
                    try:
                        progress = float(d['downloaded_bytes']) / float(d['total_bytes']) * 100
                        if self.progress_callback:
                            self.progress_callback(f"Downloading: {progress:.1f}%")
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
                    if self.progress_callback:
                        self.progress_callback("Preparing audio for transcription...")
                    
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
            if self.progress_callback:
                self.progress_callback(f"Failed to download YouTube video: {e}")
            return None, None

    def extract_audio_from_local(self, input_path, output_path, language="en-US"):
        """Extract audio from local video/audio file"""
        try:
            title = os.path.splitext(os.path.basename(input_path))[0]
            audio_file = os.path.join(output_path, f"{title}.wav")
            
            # Check if input is already an audio file
            audio_extensions = ['.mp3', '.wav', '.aac', '.ogg']
            if os.path.splitext(input_path)[1].lower() in audio_extensions:
                # Convert audio file to WAV using pydub with enhanced settings
                audio = AudioSegment.from_file(input_path)
                # Special processing for Arabic audio
                if language == "ar-AR":
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
            if self.progress_callback:
                self.progress_callback(f"Failed to extract/convert audio: {e}")
            return None, None
    
    def process_audio_stream(self, audio_path, language="en-US"):
        """Process audio in a streaming fashion while it's being downloaded/prepared"""
        try:
            chunk_size = 5 * 1000  # 5 second chunks
            audio = AudioSegment.from_wav(audio_path)
            
            # Process audio in small chunks
            chunks = make_chunks(audio, chunk_size)
            for i, chunk in enumerate(chunks):
                # Process chunk
                processed_chunk = chunk.set_channels(1).set_frame_rate(16000)
                if language == "ar-AR":
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
            if self.progress_callback:
                self.progress_callback(f"Error in audio stream processing: {e}")
    
    def prepare_audio_for_transcription(self, audio_path, language="en-US"):
        """Prepare audio with optimal settings for transcription"""
        try:
            audio = AudioSegment.from_file(audio_path)

            if language == "ar-AR":
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
            
            return audio
        except Exception as e:
            if self.progress_callback:
                self.progress_callback(f"Error preparing audio: {e}")
            return None
