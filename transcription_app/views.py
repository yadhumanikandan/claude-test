import os
import subprocess
import tempfile
import shutil
from django.shortcuts import render, redirect, get_object_or_404
from django.conf import settings
from django.contrib import messages
from .models import Transcription
from .forms import AudioUploadForm


WHISPER_CLI = os.path.join(settings.BASE_DIR, 'whisper.cpp', 'build', 'bin', 'whisper-cli')
WHISPER_MODEL = os.path.join(settings.BASE_DIR, 'whisper.cpp', 'models', 'ggml-base.en.bin')


def convert_to_wav(input_path, output_path):
    """Convert audio file to 16-bit WAV format required by whisper.cpp"""
    try:
        cmd = [
            'ffmpeg', '-y', '-i', input_path,
            '-ar', '16000', '-ac', '1', '-c:a', 'pcm_s16le',
            output_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        return result.returncode == 0, result.stderr
    except subprocess.TimeoutExpired:
        return False, "Conversion timed out"
    except Exception as e:
        return False, str(e)


def transcribe_audio(wav_path, model_path=None):
    """Transcribe audio using whisper.cpp CLI"""
    if model_path is None:
        model_path = WHISPER_MODEL

    if not os.path.exists(WHISPER_CLI):
        return False, f"Whisper CLI not found at {WHISPER_CLI}"

    if not os.path.exists(model_path):
        return False, f"Model not found at {model_path}. Please download a model first."

    try:
        cmd = [
            WHISPER_CLI,
            '-m', model_path,
            '-f', wav_path,
            '--no-timestamps',
            '-t', '4'  # Use 4 threads
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if result.returncode == 0:
            transcript = result.stdout.strip()
            lines = transcript.split('\n')
            cleaned_lines = [line.strip() for line in lines if line.strip() and not line.startswith('[')]
            return True, ' '.join(cleaned_lines)
        return False, result.stderr
    except subprocess.TimeoutExpired:
        return False, "Transcription timed out"
    except Exception as e:
        return False, str(e)


def home(request):
    """Home page with upload form and recent transcriptions"""
    if request.method == 'POST':
        form = AudioUploadForm(request.POST, request.FILES)
        if form.is_valid():
            transcription = form.save(commit=False)
            transcription.original_filename = request.FILES['audio_file'].name
            transcription.status = 'processing'
            transcription.save()

            temp_dir = tempfile.mkdtemp()
            try:
                wav_path = os.path.join(temp_dir, 'audio.wav')
                audio_path = transcription.audio_file.path

                success, error = convert_to_wav(audio_path, wav_path)
                if not success:
                    transcription.status = 'failed'
                    transcription.error_message = f"Audio conversion failed: {error}"
                    transcription.save()
                    messages.error(request, f"Failed to convert audio: {error}")
                    return redirect('transcription_detail', pk=transcription.pk)

                success, result = transcribe_audio(wav_path)
                if success:
                    transcription.transcript = result
                    transcription.status = 'completed'
                    messages.success(request, "Transcription completed successfully!")
                else:
                    transcription.status = 'failed'
                    transcription.error_message = result
                    messages.error(request, f"Transcription failed: {result}")
                transcription.save()

            finally:
                shutil.rmtree(temp_dir, ignore_errors=True)

            return redirect('transcription_detail', pk=transcription.pk)
    else:
        form = AudioUploadForm()

    recent_transcriptions = Transcription.objects.all()[:10]
    return render(request, 'transcription_app/home.html', {
        'form': form,
        'recent_transcriptions': recent_transcriptions
    })


def transcription_detail(request, pk):
    """View a specific transcription"""
    transcription = get_object_or_404(Transcription, pk=pk)
    return render(request, 'transcription_app/detail.html', {
        'transcription': transcription
    })


def transcription_list(request):
    """List all transcriptions"""
    transcriptions = Transcription.objects.all()
    return render(request, 'transcription_app/list.html', {
        'transcriptions': transcriptions
    })


def transcription_delete(request, pk):
    """Delete a transcription"""
    transcription = get_object_or_404(Transcription, pk=pk)
    if request.method == 'POST':
        if transcription.audio_file:
            if os.path.exists(transcription.audio_file.path):
                os.remove(transcription.audio_file.path)
        transcription.delete()
        messages.success(request, "Transcription deleted successfully!")
        return redirect('transcription_home')
    return render(request, 'transcription_app/confirm_delete.html', {
        'transcription': transcription
    })
