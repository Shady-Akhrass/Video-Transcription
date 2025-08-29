import tkinter as tk
import threading
import tempfile
import os
from gui import TranscriptionGUI
from audio_processor import AudioProcessor
from transcription_engine import TranscriptionEngine
from file_operations import FileOperations

class TranscriptionApp:
    def __init__(self, root):
        self.root = root
        self.gui = TranscriptionGUI(root)
        
        # Initialize components
        self.audio_processor = AudioProcessor(progress_callback=self.update_progress)
        self.transcription_engine = TranscriptionEngine(progress_callback=self.update_progress)
        self.file_operations = FileOperations()
        
        # Connect GUI methods to actual implementations
        self.gui.start_transcription = self.start_transcription
        self.gui.stop_transcription = self.stop_transcription
        self.gui.save_results = self.save_results
        
        # Set up progress callback
        self.gui.progress_callback = self.update_progress
        
    def update_progress(self, message):
        """Update progress in the GUI"""
        if hasattr(self.gui, 'progress_var'):
            self.gui.progress_var.set(message)
    
    def start_transcription(self):
        """Start the transcription process"""
        input_path = self.gui.input_var.get().strip()
        if not input_path:
            tk.messagebox.showerror("Error", "Please provide a video file or YouTube URL")
            return
        
        # Set API key if provided
        gemini_api_key = self.gui.api_key_var.get().strip()
        self.transcription_engine.set_gemini_api_key(gemini_api_key)
        self.file_operations.set_gemini_api_key(gemini_api_key)
        
        # Set translation option
        self.transcription_engine.set_translate_option(self.gui.translate_var.get())
        
        # Clear previous results
        for item in self.gui.tree.get_children():
            self.gui.tree.delete(item)
        self.gui.transcription_data = []
        self.gui.current_text.delete(1.0, tk.END)
        
        # Update UI state
        self.gui.is_transcribing = True
        self.gui.start_button.config(state=tk.DISABLED)
        self.gui.stop_button.config(state=tk.NORMAL)
        self.gui.save_button.config(state=tk.DISABLED)
        self.gui.progress_bar["value"] = 0
        self.gui.progress_var.set("Preparing...")
        
        # Start transcription in a separate thread
        thread = threading.Thread(target=self.transcription_worker, args=(input_path,))
        thread.daemon = True
        thread.start()
    
    def transcription_worker(self, input_path):
        """Worker thread for transcription"""
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                is_youtube = self.audio_processor.is_youtube_url(input_path)
                
                if is_youtube:
                    self.root.after(0, lambda: self.gui.progress_var.set("Downloading YouTube audio..."))
                    audio_path, title = self.audio_processor.download_youtube_audio(input_path, tmpdir)
                else:
                    self.root.after(0, lambda: self.gui.progress_var.set("Extracting audio..."))
                    language = self.gui.language_var.get()
                    audio_path, title = self.audio_processor.extract_audio_from_local(input_path, tmpdir, language)
                
                if not audio_path or not self.gui.is_transcribing:
                    return
                
                # Start transcription
                self.root.after(0, lambda: self.gui.progress_var.set("Starting transcription..."))
                
                # Get segment length
                try:
                    segment_length_sec = float(self.gui.segment_length.get())
                except ValueError:
                    segment_length_sec = 15.0
                
                # Perform transcription
                transcription_data = self.transcription_engine.transcribe_audio_segments(
                    audio_path, 
                    segment_length_sec, 
                    self.gui.is_transcribing
                )
                
                # Update GUI with results
                if transcription_data:
                    self.gui.transcription_data = transcription_data
                    for segment in transcription_data:
                        self.root.after(0, lambda s=segment: (
                            self.gui.add_to_tree(s),
                            self.gui.update_current_display(s['english'], s['arabic'])
                        ))
                
        except Exception as e:
            self.root.after(0, lambda: tk.messagebox.showerror("Error", f"Transcription failed: {e}"))
        finally:
            self.root.after(0, self.transcription_finished)
    
    def transcription_finished(self):
        """Called when transcription is finished"""
        self.gui.transcription_finished()
    
    def stop_transcription(self):
        """Stop the transcription process"""
        self.gui.is_transcribing = False
        self.gui.progress_var.set("Stopping...")
    
    def save_results(self):
        """Save transcription results"""
        if not self.gui.transcription_data:
            tk.messagebox.showwarning("Warning", "No transcription data to save")
            return
        
        # Use file operations to save results
        success = self.file_operations.save_results(self.gui.transcription_data, self.root)
        if success:
            # Update the save button state
            self.gui.save_button.config(state=tk.NORMAL)

def main():
    root = tk.Tk()
    app = TranscriptionApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
