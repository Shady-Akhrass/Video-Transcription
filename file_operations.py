import os
import json
import google.generativeai as genai
from tkinter import filedialog, messagebox

class FileOperations:
    def __init__(self, gemini_api_key=""):
        self.gemini_api_key = gemini_api_key
        
    def set_gemini_api_key(self, api_key):
        """Set the Gemini API key for translation"""
        self.gemini_api_key = api_key
        
    def save_results(self, transcription_data, parent_window=None):
        """Save transcription results to multiple file formats"""
        if not transcription_data:
            if parent_window:
                messagebox.showwarning("Warning", "No transcription data to save")
            return False
        
        # Ask for save location
        base_filename = filedialog.asksaveasfilename(
            title="Save Transcription Results",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if not base_filename:
            return False
        
        try:
            base_name = os.path.splitext(base_filename)[0]
            
            # Save timestamps and English text
            with open(f"{base_name}_timestamps.txt", "w", encoding="utf-8") as f:
                for segment in transcription_data:
                    f.write(f"{segment['timestamp']}: {segment['english']}\n")
            
            # Save English text only
            with open(f"{base_name}_english.txt", "w", encoding="utf-8") as f:
                for segment in transcription_data:
                    if segment['english'] and not segment['english'].startswith('['):
                        f.write(f"{segment['english']} ")
            
            # Save Arabic translation if available with Gemini AI correction
            if any(segment['arabic'] for segment in transcription_data):
                # Collect all Arabic text for batch correction
                arabic_text = " ".join([
                    segment['arabic'] 
                    for segment in transcription_data 
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
                        valid_segments = [s for s in transcription_data if s['arabic'] and not s['arabic'].startswith('[')]
                        
                        # Try to match corrected lines with segments based on content similarity
                        current_line = 0
                        for segment in valid_segments:
                            if current_line < len(corrected_lines):
                                segment['arabic'] = corrected_lines[current_line].strip()
                                current_line += 1
                        
                        for segment in transcription_data:
                            if segment['arabic'] and not segment['arabic'].startswith('['):
                                segment['arabic'] = corrected_lines[current_line].strip()
                                current_line += 1
                                
                except Exception as e:
                    print(f"Arabic correction error: {e}")
                    # Fallback to original text if correction fails
                    with open(f"{base_name}_arabic.txt", "w", encoding="utf-8") as f:
                        for segment in transcription_data:
                            if segment['arabic'] and not segment['arabic'].startswith('['):
                                f.write(f"{segment['arabic']} ")
            
            # Save complete data as JSON
            with open(f"{base_name}_complete.json", "w", encoding="utf-8") as f:
                json.dump(transcription_data, f, ensure_ascii=False, indent=2)
            
            if parent_window:
                messagebox.showinfo("Success", f"Results saved to:\n"
                                             f"• {base_name}_timestamps.txt\n"
                                             f"• {base_name}_english.txt\n" +
                                             (f"• {base_name}_arabic.txt\n" if any(s['arabic'] for s in transcription_data) else "") +
                                             f"• {base_name}_complete.json")
            
            return True
        
        except Exception as e:
            if parent_window:
                messagebox.showerror("Error", f"Failed to save results: {e}")
            return False
    
    def load_transcription_data(self, file_path):
        """Load transcription data from a JSON file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading transcription data: {e}")
            return None
    
    def export_to_srt(self, transcription_data, output_path):
        """Export transcription data to SRT subtitle format"""
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                for i, segment in enumerate(transcription_data, 1):
                    # Parse timestamp
                    timestamp = segment['timestamp']
                    if ':' in timestamp:
                        # Convert HH:MM:SS to SRT format
                        time_parts = timestamp.split(':')
                        if len(time_parts) == 3:
                            hours, minutes, seconds = map(int, time_parts)
                            start_time = f"{hours:02d}:{minutes:02d}:{seconds:02d},000"
                            end_time = f"{hours:02d}:{minutes:02d}:{seconds+15:02d},000"
                        else:
                            start_time = "00:00:00,000"
                            end_time = "00:00:15,000"
                    else:
                        start_time = "00:00:00,000"
                        end_time = "00:00:15,000"
                    
                    # Write SRT entry
                    f.write(f"{i}\n")
                    f.write(f"{start_time} --> {end_time}\n")
                    f.write(f"{segment['english']}\n\n")
            
            return True
        except Exception as e:
            print(f"Error exporting to SRT: {e}")
            return False
    
    def export_to_vtt(self, transcription_data, output_path):
        """Export transcription data to WebVTT format"""
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write("WEBVTT\n\n")
                
                for i, segment in enumerate(transcription_data, 1):
                    # Parse timestamp
                    timestamp = segment['timestamp']
                    if ':' in timestamp:
                        time_parts = timestamp.split(':')
                        if len(time_parts) == 3:
                            hours, minutes, seconds = map(int, time_parts)
                            start_time = f"{hours:02d}:{minutes:02d}:{seconds:02d}.000"
                            end_time = f"{hours:02d}:{minutes:02d}:{seconds+15:02d}.000"
                        else:
                            start_time = "00:00:00.000"
                            end_time = "00:00:15.000"
                    else:
                        start_time = "00:00:00.000"
                        end_time = "00:00:15.000"
                    
                    # Write VTT entry
                    f.write(f"{start_time} --> {end_time}\n")
                    f.write(f"{segment['english']}\n\n")
            
            return True
        except Exception as e:
            print(f"Error exporting to VTT: {e}")
            return False
