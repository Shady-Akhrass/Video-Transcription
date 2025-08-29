# Video Transcription Tool with Translation

A modular Python application for transcribing video/audio files with support for English and Arabic, including translation capabilities using Google Gemini AI.

## Project Structure

The application has been separated into logical modules for better maintainability:

### Core Modules

- **`gui.py`** - User interface components and layout
- **`audio_processor.py`** - Audio processing, YouTube download, and file conversion
- **`transcription_engine.py`** - Speech recognition and translation engine
- **`file_operations.py`** - File saving, loading, and export operations
- **`main_app.py`** - Main application that integrates all modules

### Entry Point

- **`main.py`** - Original monolithic file (kept for reference)
- **`main_app.py`** - New modular entry point

## Features

- **Multi-format Support**: MP4, AVI, MKV, MOV, WMV, FLV, WebM, MP3, WAV, AAC, OGG
- **YouTube Integration**: Direct URL processing with yt-dlp
- **Language Support**: English and Arabic transcription
- **Translation**: Google Gemini AI-powered translation between languages
- **Export Formats**: TXT, JSON, SRT, VTT
- **Real-time Processing**: Streaming audio processing with progress tracking
- **Text Formatting**: Bold, italic, and timestamp insertion support

## Installation

1. Install Python 3.8 or higher
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Install FFmpeg (required for audio processing):
   - Windows: Download from https://ffmpeg.org/download.html
   - macOS: `brew install ffmpeg`
   - Linux: `sudo apt install ffmpeg`

## Usage

### Running the Application

```bash
python main_app.py
```

### Basic Workflow

1. **Input**: Provide a video file path or YouTube URL
2. **Configuration**: 
   - Set language (English/Arabic)
   - Configure segment length (5-60 seconds)
   - Add Google Gemini API key for translation (optional)
3. **Processing**: Click "Start Transcription" to begin
4. **Results**: View results in the tree view and edit in the current segment panel
5. **Export**: Save results in multiple formats

### Keyboard Shortcuts

- **Ctrl+B**: Bold text
- **Ctrl+I**: Italic text
- **Ctrl+K**: Insert [inaudible] timestamp
- **Ctrl+L**: Insert [unintelligible] timestamp

## API Configuration

For translation features, you'll need a Google Gemini API key:

1. Visit [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Create an API key
3. Enter the key in the application's API Key field

## Module Details

### GUI Module (`gui.py`)
- Main window layout and widgets
- Event handling and user interactions
- Text formatting and keyboard shortcuts
- Progress tracking display

### Audio Processor (`audio_processor.py`)
- YouTube video download using yt-dlp
- Audio extraction from video files
- Audio format conversion and optimization
- Language-specific audio processing

### Transcription Engine (`transcription_engine.py`)
- Google Speech Recognition for English
- OpenAI Whisper for Arabic
- Parallel processing with thread pools
- Text post-processing and formatting

### File Operations (`file_operations.py`)
- Multi-format export (TXT, JSON, SRT, VTT)
- Arabic text correction using Gemini AI
- Timestamp formatting and conversion
- File loading and validation

## Performance Considerations

- **English**: Uses Google Speech Recognition with parallel processing
- **Arabic**: Uses Whisper model with single-threaded processing for stability
- **Memory**: Processes audio in configurable segments to manage memory usage
- **Threading**: Configurable worker threads based on CPU cores

## Error Handling

- Graceful fallback for API failures
- Temporary file cleanup on errors
- User-friendly error messages
- Progress tracking during long operations

## Contributing

The modular structure makes it easy to:
- Add new audio formats
- Implement additional transcription engines
- Extend export formats
- Modify the user interface

## License

This project is open source. Please check individual dependency licenses for compliance. 