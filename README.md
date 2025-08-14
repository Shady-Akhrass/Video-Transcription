## Video Transcription Tool with Translation

A desktop GUI app (Tkinter) that transcribes audio/video files or YouTube URLs into text, with optional English↔Arabic translation and Arabic text correction using Google Gemini. It segments audio, shows progress, and lets you review/edit current segments quickly.

### Features
- **Local or YouTube input**: Pick a file or paste a YouTube URL (uses `yt-dlp`).
- **English mode**: Transcribes with Google Speech Recognition via `SpeechRecognition`.
- **Arabic mode**: Transcribes with OpenAI Whisper (`openai-whisper`).
- **Optional translation**: Uses Google Gemini for English→Arabic (or Arabic→English) translation.
- **Batch save**: Exports timestamps, English-only, Arabic-corrected, and a complete JSON.
- **Keyboard shortcuts**: Quick bold/italic and insert `[inaudible]` / `[unintelligible]` markers.
- **Segment length**: Choose how long each segment is for processing.

## Requirements
- **Python**: 3.9+ recommended
- **FFmpeg**: Required by `moviepy` and `pydub`
- **Internet access**: For YouTube downloads and cloud recognition/translation
- **Optional**: Google Gemini API key for translation and Arabic text correction

### Install FFmpeg (Windows)
- With Winget:
```powershell
winget install FFmpeg.FFmpeg
```
- Or with Chocolatey:
```powershell
choco install ffmpeg -y
```
After install, open a new terminal and verify:
```powershell
ffmpeg -version
```

## Installation
From a PowerShell terminal in the project folder:

```powershell
# (Recommended) Create and activate a virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Upgrade pip
python -m pip install --upgrade pip

# Install core dependencies
pip install yt-dlp moviepy pydub SpeechRecognition google-generativeai openai-whisper

# Install PyTorch (choose ONE of the following):
# CPU-only (simplest):
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

# For NVIDIA GPU (example for CUDA 12.1; see PyTorch site for other versions):
# pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

Notes:
- If `openai-whisper` complains about missing PyTorch, install PyTorch first, then reinstall Whisper.
- On first run, Whisper will download the selected model.

## Running the App
```powershell
python main.py
```

### Quick Start
1. **Input**: Browse for an audio/video file or paste a YouTube URL.
2. **Language**: Select `English` or `Arabic`.
3. **(Optional) Translation**: Tick “Translate to Arabic” (English mode) or to English (Arabic mode).
4. **(Optional) API key**: Paste your Google Gemini API key if translation/correction is desired.
5. **Segment length**: Choose a duration (e.g., 15s).
6. **Start**: Click “Start Transcription”.
7. **Review**: Monitor progress, click any row to load its texts into the editors.
8. **Save**: Click “Save Results” to export outputs.

### What happens under the hood
- **English mode**: Uses `SpeechRecognition` → Google Speech Recognition API.
- **Arabic mode**: Uses `openai-whisper` (model `medium` by default).
- **Translation**: Uses Google Gemini (`gemini-2.0-flash`).
- **YouTube**: Downloads best audio via `yt-dlp`, converts to WAV, and segments.

## Outputs
When you save, these files are created next to your chosen base name:
- `..._timestamps.txt`: Timestamped English lines
- `..._english.txt`: English text only (non-bracketed entries)
- `..._arabic.txt`: Arabic text, optionally corrected by Gemini and formatted for conversations
- `..._complete.json`: Full structured data for all segments

Arabic correction uses Gemini if an API key is provided. It preserves speaker markers and line breaks.

## Configuration Tips
- **Model size for Arabic**: The Whisper model is set to `"medium"` in `main.py`. On low-spec machines you may change it to `"small"` or `"base"`:
  - Look for `whisper.load_model("medium")` and adjust as needed.
- **Segment length**: Shorter segments improve responsiveness but add more API calls.
- **Translation**: Requires a valid Gemini API key; otherwise placeholders are shown.

## Troubleshooting
- **FFmpeg not found**: Ensure `ffmpeg -version` works in a new terminal. Reinstall via Winget/Chocolatey and confirm your PATH.
- **PyTorch/Whisper errors**: Install PyTorch first (CPU or GPU variant), then `openai-whisper`.
- **Google SpeechRecognition errors**: These can be temporary quota/network errors; retry or switch to local Whisper (Arabic mode) if appropriate.
- **yt-dlp download issues**: Some videos are geo-restricted/age-gated. Update `yt-dlp` (`pip install -U yt-dlp`) and ensure network access.
- **Slow or high CPU usage**: Use shorter segments, reduce background apps, or switch Whisper model to `small`/`base`.

## Privacy & Security
- API keys are only used in-memory during a session and not stored by the app. Do not commit keys to source control.

## License
No license specified. Consider adding one if you plan to share or publish this project. 