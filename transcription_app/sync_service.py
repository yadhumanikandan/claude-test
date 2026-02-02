"""
Sync Service for Yeastar PBX Call Recordings

Handles fetching CDRs, downloading recordings, and triggering transcriptions.
"""

import os
import logging
import tempfile
import shutil
from datetime import datetime, timedelta
from django.conf import settings
from django.core.files.base import ContentFile
from django.utils import timezone

from .models import YeastarPBXConfig, CDRRecord, Transcription
from .yeastar_client import YeastarClient, YeastarAPIError

logger = logging.getLogger(__name__)

# Whisper paths
WHISPER_CLI = os.path.join(settings.BASE_DIR, 'whisper.cpp', 'build', 'bin', 'whisper-cli')
WHISPER_MODEL = os.path.join(settings.BASE_DIR, 'whisper.cpp', 'models', 'ggml-base.en.bin')


class SyncService:
    """Service for syncing recordings from Yeastar PBX"""

    def __init__(self, pbx_config: YeastarPBXConfig):
        self.pbx_config = pbx_config
        self.client = YeastarClient(pbx_config)
        self.stats = {
            'cdr_fetched': 0,
            'cdr_new': 0,
            'recordings_downloaded': 0,
            'transcriptions_created': 0,
            'errors': []
        }

    def sync_cdr(
        self,
        start_time: datetime = None,
        end_time: datetime = None,
        download_recordings: bool = True,
        transcribe: bool = True
    ) -> dict:
        """
        Sync CDR records from PBX.

        Args:
            start_time: Start time for CDR query (default: last sync or 24h ago)
            end_time: End time for CDR query (default: now)
            download_recordings: Whether to download recording files
            transcribe: Whether to transcribe downloaded recordings

        Returns:
            dict: Sync statistics
        """
        # Set default time range
        if not end_time:
            end_time = timezone.now()
        if not start_time:
            if self.pbx_config.last_sync_at:
                start_time = self.pbx_config.last_sync_at
            else:
                start_time = end_time - timedelta(hours=24)

        logger.info(f"Starting CDR sync for {self.pbx_config.name} from {start_time} to {end_time}")

        try:
            # Fetch CDR records
            cdr_records = self.client.get_cdr(start_time=start_time, end_time=end_time)
            self.stats['cdr_fetched'] = len(cdr_records)
            logger.info(f"Fetched {len(cdr_records)} CDR records")

            # Process each CDR record
            for cdr_data in cdr_records:
                try:
                    cdr_record = self._process_cdr_record(cdr_data)
                    if cdr_record:
                        self.stats['cdr_new'] += 1

                        # Download recording if available
                        if download_recordings and cdr_record.recording_file:
                            transcription = self._download_and_create_transcription(cdr_record)
                            if transcription and transcribe:
                                self._transcribe_recording(transcription)

                except Exception as e:
                    logger.error(f"Error processing CDR: {e}")
                    self.stats['errors'].append(str(e))

            # Update last sync time
            self.pbx_config.last_sync_at = timezone.now()
            self.pbx_config.save(update_fields=['last_sync_at'])

        except YeastarAPIError as e:
            logger.error(f"API error during sync: {e}")
            self.stats['errors'].append(str(e))
        finally:
            try:
                self.client.logout()
            except Exception:
                pass

        return self.stats

    def _process_cdr_record(self, cdr_data: dict) -> CDRRecord:
        """
        Process and save a CDR record.

        Args:
            cdr_data: CDR data dictionary

        Returns:
            CDRRecord or None if already exists
        """
        call_id = cdr_data.get('id')
        if not call_id:
            # Generate a call_id from other fields
            call_id = f"{cdr_data.get('time', '')}-{cdr_data.get('caller', '')}-{cdr_data.get('callee', '')}"

        # Check if already exists
        if CDRRecord.objects.filter(call_id=call_id).exists():
            return None

        # Parse call time
        call_time = None
        time_str = cdr_data.get('time', '')
        if time_str:
            try:
                call_time = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
                call_time = timezone.make_aware(call_time)
            except ValueError:
                pass

        # Create CDR record
        cdr_record = CDRRecord.objects.create(
            pbx_config=self.pbx_config,
            call_id=call_id,
            caller=cdr_data.get('caller', ''),
            callee=cdr_data.get('callee', ''),
            call_from=cdr_data.get('call_from', ''),
            call_to=cdr_data.get('call_to', ''),
            duration=cdr_data.get('duration', 0),
            talk_duration=cdr_data.get('talk_duration', 0),
            call_type=cdr_data.get('call_type', ''),
            status=cdr_data.get('status', ''),
            recording_file=cdr_data.get('recording', ''),
            call_time=call_time,
            raw_data=cdr_data
        )

        logger.info(f"Created CDR record: {cdr_record}")
        return cdr_record

    def _download_and_create_transcription(self, cdr_record: CDRRecord) -> Transcription:
        """
        Download recording and create transcription record.

        Args:
            cdr_record: CDR record with recording file

        Returns:
            Transcription record or None
        """
        if not cdr_record.recording_file:
            return None

        # Check if transcription already exists
        if hasattr(cdr_record, 'transcription') and cdr_record.transcription:
            return cdr_record.transcription

        try:
            logger.info(f"Downloading recording: {cdr_record.recording_file}")

            # Create transcription record first
            transcription = Transcription.objects.create(
                original_filename=cdr_record.recording_file,
                status='downloading',
                source='yeastar',
                cdr_record=cdr_record
            )

            # Download the recording
            recording_content = self.client.download_recording(cdr_record.recording_file)

            # Save to file
            filename = os.path.basename(cdr_record.recording_file)
            transcription.audio_file.save(filename, ContentFile(recording_content))
            transcription.status = 'pending'
            transcription.save()

            self.stats['recordings_downloaded'] += 1
            logger.info(f"Downloaded recording: {filename}")

            return transcription

        except YeastarAPIError as e:
            logger.error(f"Failed to download recording: {e}")
            if transcription:
                transcription.status = 'failed'
                transcription.error_message = f"Download failed: {e}"
                transcription.save()
            self.stats['errors'].append(f"Download error: {e}")
            return None

    def _transcribe_recording(self, transcription: Transcription):
        """
        Transcribe a recording using whisper.cpp

        Args:
            transcription: Transcription record to process
        """
        import subprocess

        if not os.path.exists(WHISPER_CLI):
            logger.error(f"Whisper CLI not found: {WHISPER_CLI}")
            transcription.status = 'failed'
            transcription.error_message = "Whisper CLI not found"
            transcription.save()
            return

        if not os.path.exists(WHISPER_MODEL):
            logger.error(f"Whisper model not found: {WHISPER_MODEL}")
            transcription.status = 'failed'
            transcription.error_message = "Whisper model not found"
            transcription.save()
            return

        transcription.status = 'processing'
        transcription.save()

        temp_dir = tempfile.mkdtemp()
        try:
            wav_path = os.path.join(temp_dir, 'audio.wav')
            audio_path = transcription.audio_file.path

            # Convert to WAV
            convert_cmd = [
                'ffmpeg', '-y', '-i', audio_path,
                '-ar', '16000', '-ac', '1', '-c:a', 'pcm_s16le',
                wav_path
            ]
            result = subprocess.run(convert_cmd, capture_output=True, text=True, timeout=300)

            if result.returncode != 0:
                transcription.status = 'failed'
                transcription.error_message = f"Audio conversion failed: {result.stderr}"
                transcription.save()
                return

            # Transcribe
            transcribe_cmd = [
                WHISPER_CLI,
                '-m', WHISPER_MODEL,
                '-f', wav_path,
                '--no-timestamps',
                '-t', '4'
            ]
            result = subprocess.run(transcribe_cmd, capture_output=True, text=True, timeout=600)

            if result.returncode == 0:
                transcript = result.stdout.strip()
                lines = transcript.split('\n')
                cleaned_lines = [line.strip() for line in lines if line.strip() and not line.startswith('[')]
                transcription.transcript = ' '.join(cleaned_lines)
                transcription.status = 'completed'
                self.stats['transcriptions_created'] += 1
                logger.info(f"Transcription completed for: {transcription.original_filename}")
            else:
                transcription.status = 'failed'
                transcription.error_message = f"Transcription failed: {result.stderr}"

            transcription.save()

        except subprocess.TimeoutExpired:
            transcription.status = 'failed'
            transcription.error_message = "Transcription timed out"
            transcription.save()
        except Exception as e:
            transcription.status = 'failed'
            transcription.error_message = str(e)
            transcription.save()
            logger.error(f"Transcription error: {e}")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


def sync_all_pbx(download_recordings=True, transcribe=True):
    """
    Sync all active PBX configurations.

    Returns:
        dict: Combined stats from all syncs
    """
    combined_stats = {
        'pbx_synced': 0,
        'cdr_fetched': 0,
        'cdr_new': 0,
        'recordings_downloaded': 0,
        'transcriptions_created': 0,
        'errors': []
    }

    for pbx_config in YeastarPBXConfig.objects.filter(is_active=True):
        logger.info(f"Syncing PBX: {pbx_config.name}")
        service = SyncService(pbx_config)
        stats = service.sync_cdr(
            download_recordings=download_recordings,
            transcribe=transcribe
        )

        combined_stats['pbx_synced'] += 1
        combined_stats['cdr_fetched'] += stats['cdr_fetched']
        combined_stats['cdr_new'] += stats['cdr_new']
        combined_stats['recordings_downloaded'] += stats['recordings_downloaded']
        combined_stats['transcriptions_created'] += stats['transcriptions_created']
        combined_stats['errors'].extend(stats['errors'])

    return combined_stats


def sync_single_pbx(pbx_config_id: int, **kwargs) -> dict:
    """
    Sync a single PBX configuration by ID.

    Args:
        pbx_config_id: ID of YeastarPBXConfig

    Returns:
        dict: Sync statistics
    """
    pbx_config = YeastarPBXConfig.objects.get(id=pbx_config_id)
    service = SyncService(pbx_config)
    return service.sync_cdr(**kwargs)
