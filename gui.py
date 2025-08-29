import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import time
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
import re
import json

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
    
    def start_transcription(self):
        # This will be implemented in the main application
        pass
    
    def stop_transcription(self):
        # This will be implemented in the main application
        pass
    
    def save_results(self):
        # This will be implemented in the main application
        pass
    
    def transcription_finished(self):
        self.is_transcribing = False
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.save_button.config(state=tk.NORMAL)
        self.progress_bar["value"] = self.progress_bar["maximum"]
        self.progress_var.set("Transcription completed")
        
        if self.transcription_data:
            messagebox.showinfo("Success", f"Transcription completed! {len(self.transcription_data)} segments processed.")
