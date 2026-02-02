# Django Multi-App Project

A Django project featuring a beautiful calendar application and an audio transcription app powered by whisper.cpp.

## Applications

### 1. Whisper Transcription App (Home)

A web application for transcribing call recordings using [whisper.cpp](https://github.com/ggml-org/whisper.cpp).

**Features:**
- Upload audio files (MP3, WAV, M4A, OGG, FLAC, WebM)
- Automatic audio conversion to WAV format using ffmpeg
- Transcription using whisper.cpp
- View and manage transcription history
- Copy transcripts to clipboard
- Beautiful dark-themed UI

### 2. Calendar App

A simple and beautifully designed Django application for displaying a calendar.

**Features:**
- Modern gradient-based UI with smooth animations
- Monthly view in a clean grid format
- Today highlighting with distinctive style
- Easy navigation between months
- Responsive design

## Installation

### Prerequisites

- Python 3.11+
- ffmpeg (for audio conversion)
- cmake and build tools (for whisper.cpp)

### Setup

1. Install system dependencies:
```bash
# Ubuntu/Debian
apt-get install ffmpeg cmake build-essential

# macOS
brew install ffmpeg cmake
```

2. Install Python dependencies:
```bash
pip install django
```

3. Clone and build whisper.cpp:
```bash
git clone https://github.com/ggml-org/whisper.cpp.git
cd whisper.cpp
cmake -B build
cmake --build build -j --config Release
```

4. Download a whisper model (base.en recommended for English):
```bash
cd whisper.cpp
bash ./models/download-ggml-model.sh base.en
```

5. Run Django migrations:
```bash
python manage.py migrate
```

## Running the Application

Start the development server:
```bash
python manage.py runserver
```

Then open your browser:
- **Transcription App**: http://127.0.0.1:8000/
- **Calendar App**: http://127.0.0.1:8000/calendar/
- **Admin**: http://127.0.0.1:8000/admin/

## Project Structure

```
project/
├── transcription_app/      # Audio transcription application
│   ├── templates/          # HTML templates
│   ├── views.py            # Transcription views
│   ├── models.py           # Transcription model
│   ├── forms.py            # Upload form
│   └── urls.py             # App URL configuration
├── calendar_app/           # Calendar application
│   ├── templates/          # HTML templates
│   ├── views.py            # Calendar views
│   └── urls.py             # App URL configuration
├── calendar_project/       # Project settings
│   ├── settings.py         # Django settings
│   └── urls.py             # Main URL configuration
├── whisper.cpp/            # Whisper.cpp (external)
│   ├── build/bin/          # Compiled binaries
│   └── models/             # Model files
├── media/                  # Uploaded files
└── manage.py               # Django management script
```

## Transcription App Usage

1. Navigate to the home page
2. Click to select or drag-and-drop an audio file
3. Click "Transcribe Audio"
4. Wait for processing (conversion + transcription)
5. View the transcript and copy if needed

### Supported Audio Formats
- MP3
- WAV
- M4A
- OGG
- FLAC
- WebM
- MP4/MPEG

### Model Configuration

The app uses the `ggml-base.en.bin` model by default. To use a different model, edit the `WHISPER_MODEL` path in `transcription_app/views.py`.

Available models:
- `tiny.en` / `tiny` - Fastest, least accurate
- `base.en` / `base` - Good balance (recommended)
- `small.en` / `small` - More accurate
- `medium.en` / `medium` - High accuracy
- `large` - Best accuracy, slowest

## Technology Stack

- **Backend**: Django 5.2
- **Transcription**: whisper.cpp
- **Audio Processing**: ffmpeg
- **Frontend**: HTML5, CSS3, JavaScript
- **Database**: SQLite

## License

This is a demonstration project for educational purposes.
