import os
import subprocess
import tempfile
import shutil
from datetime import timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.conf import settings
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST
from .models import Transcription, YeastarPBXConfig, CDRRecord
from .forms import AudioUploadForm, YeastarPBXConfigForm


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
    pbx_configs = YeastarPBXConfig.objects.filter(is_active=True)

    return render(request, 'transcription_app/home.html', {
        'form': form,
        'recent_transcriptions': recent_transcriptions,
        'pbx_configs': pbx_configs
    })


def transcription_detail(request, pk):
    """View a specific transcription"""
    transcription = get_object_or_404(Transcription, pk=pk)
    return render(request, 'transcription_app/detail.html', {
        'transcription': transcription
    })


def transcription_list(request):
    """List all transcriptions"""
    source_filter = request.GET.get('source', '')
    status_filter = request.GET.get('status', '')

    transcriptions = Transcription.objects.all()

    if source_filter:
        transcriptions = transcriptions.filter(source=source_filter)
    if status_filter:
        transcriptions = transcriptions.filter(status=status_filter)

    return render(request, 'transcription_app/list.html', {
        'transcriptions': transcriptions,
        'source_filter': source_filter,
        'status_filter': status_filter
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


# PBX Configuration Views

def pbx_settings(request):
    """PBX settings page"""
    pbx_configs = YeastarPBXConfig.objects.all()
    return render(request, 'transcription_app/pbx_settings.html', {
        'pbx_configs': pbx_configs
    })


def pbx_add(request):
    """Add new PBX configuration"""
    if request.method == 'POST':
        form = YeastarPBXConfigForm(request.POST)
        if form.is_valid():
            pbx_config = form.save()
            messages.success(request, f"PBX '{pbx_config.name}' added successfully!")
            return redirect('pbx_settings')
    else:
        form = YeastarPBXConfigForm()

    return render(request, 'transcription_app/pbx_form.html', {
        'form': form,
        'title': 'Add PBX Configuration'
    })


def pbx_edit(request, pk):
    """Edit PBX configuration"""
    pbx_config = get_object_or_404(YeastarPBXConfig, pk=pk)

    if request.method == 'POST':
        form = YeastarPBXConfigForm(request.POST, instance=pbx_config)
        if form.is_valid():
            form.save()
            messages.success(request, f"PBX '{pbx_config.name}' updated successfully!")
            return redirect('pbx_settings')
    else:
        form = YeastarPBXConfigForm(instance=pbx_config)

    return render(request, 'transcription_app/pbx_form.html', {
        'form': form,
        'title': f'Edit {pbx_config.name}',
        'pbx_config': pbx_config
    })


def pbx_delete(request, pk):
    """Delete PBX configuration"""
    pbx_config = get_object_or_404(YeastarPBXConfig, pk=pk)

    if request.method == 'POST':
        name = pbx_config.name
        pbx_config.delete()
        messages.success(request, f"PBX '{name}' deleted successfully!")
        return redirect('pbx_settings')

    return render(request, 'transcription_app/pbx_confirm_delete.html', {
        'pbx_config': pbx_config
    })


@require_POST
def pbx_test_connection(request, pk):
    """Test PBX connection"""
    from .yeastar_client import YeastarClient

    pbx_config = get_object_or_404(YeastarPBXConfig, pk=pk)
    client = YeastarClient(pbx_config)
    result = client.test_connection()

    return JsonResponse(result)


@require_POST
def pbx_sync(request, pk):
    """Sync recordings from PBX"""
    from .sync_service import SyncService

    pbx_config = get_object_or_404(YeastarPBXConfig, pk=pk)

    # Get hours from request, default to 24
    hours = int(request.POST.get('hours', 24))
    end_time = timezone.now()
    start_time = end_time - timedelta(hours=hours)

    service = SyncService(pbx_config)
    stats = service.sync_cdr(
        start_time=start_time,
        end_time=end_time,
        download_recordings=True,
        transcribe=True
    )

    if stats['errors']:
        messages.warning(
            request,
            f"Sync completed with errors. CDR: {stats['cdr_new']}, "
            f"Recordings: {stats['recordings_downloaded']}, "
            f"Transcriptions: {stats['transcriptions_created']}"
        )
    else:
        messages.success(
            request,
            f"Sync completed! New CDR: {stats['cdr_new']}, "
            f"Recordings: {stats['recordings_downloaded']}, "
            f"Transcriptions: {stats['transcriptions_created']}"
        )

    return redirect('pbx_settings')


def cdr_list(request):
    """List CDR records"""
    pbx_filter = request.GET.get('pbx', '')
    cdr_records = CDRRecord.objects.all()

    if pbx_filter:
        cdr_records = cdr_records.filter(pbx_config_id=pbx_filter)

    pbx_configs = YeastarPBXConfig.objects.all()

    return render(request, 'transcription_app/cdr_list.html', {
        'cdr_records': cdr_records[:100],
        'pbx_configs': pbx_configs,
        'pbx_filter': pbx_filter
    })
