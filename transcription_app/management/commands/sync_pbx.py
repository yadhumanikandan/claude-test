"""
Django management command to sync call recordings from Yeastar PBX.

Usage:
    python manage.py sync_pbx                    # Sync all active PBX configs
    python manage.py sync_pbx --pbx-id=1         # Sync specific PBX
    python manage.py sync_pbx --no-transcribe    # Download only, no transcription
    python manage.py sync_pbx --hours=48         # Sync last 48 hours
"""

from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone

from transcription_app.models import YeastarPBXConfig
from transcription_app.sync_service import SyncService, sync_all_pbx


class Command(BaseCommand):
    help = 'Sync call recordings from Yeastar PBX'

    def add_arguments(self, parser):
        parser.add_argument(
            '--pbx-id',
            type=int,
            help='Sync only this PBX configuration ID'
        )
        parser.add_argument(
            '--hours',
            type=int,
            default=24,
            help='Number of hours to look back for recordings (default: 24)'
        )
        parser.add_argument(
            '--no-download',
            action='store_true',
            help='Only fetch CDR, do not download recordings'
        )
        parser.add_argument(
            '--no-transcribe',
            action='store_true',
            help='Download recordings but do not transcribe'
        )
        parser.add_argument(
            '--list',
            action='store_true',
            help='List all configured PBX systems'
        )
        parser.add_argument(
            '--test',
            action='store_true',
            help='Test connection to PBX without syncing'
        )

    def handle(self, *args, **options):
        # List PBX configurations
        if options['list']:
            self._list_pbx_configs()
            return

        # Test connection
        if options['test']:
            self._test_connections(options.get('pbx_id'))
            return

        # Sync options
        download_recordings = not options['no_download']
        transcribe = not options['no_transcribe'] and download_recordings
        hours = options['hours']

        end_time = timezone.now()
        start_time = end_time - timedelta(hours=hours)

        if options['pbx_id']:
            # Sync specific PBX
            self._sync_single_pbx(
                options['pbx_id'],
                start_time,
                end_time,
                download_recordings,
                transcribe
            )
        else:
            # Sync all active PBX configs
            self._sync_all_pbx(
                start_time,
                end_time,
                download_recordings,
                transcribe
            )

    def _list_pbx_configs(self):
        """List all PBX configurations"""
        configs = YeastarPBXConfig.objects.all()

        if not configs.exists():
            self.stdout.write(self.style.WARNING('No PBX configurations found.'))
            self.stdout.write('Add a configuration via Django admin or the web interface.')
            return

        self.stdout.write(self.style.SUCCESS('\nConfigured PBX Systems:\n'))
        for config in configs:
            status = 'Active' if config.is_active else 'Inactive'
            auto_sync = 'Yes' if config.auto_sync else 'No'
            last_sync = config.last_sync_at.strftime('%Y-%m-%d %H:%M') if config.last_sync_at else 'Never'

            self.stdout.write(f"  ID: {config.id}")
            self.stdout.write(f"  Name: {config.name}")
            self.stdout.write(f"  Host: {config.host}:{config.port}")
            self.stdout.write(f"  Status: {status}")
            self.stdout.write(f"  Auto-sync: {auto_sync}")
            self.stdout.write(f"  Last sync: {last_sync}")
            self.stdout.write('')

    def _test_connections(self, pbx_id=None):
        """Test PBX connections"""
        from transcription_app.yeastar_client import YeastarClient

        if pbx_id:
            configs = YeastarPBXConfig.objects.filter(id=pbx_id)
        else:
            configs = YeastarPBXConfig.objects.filter(is_active=True)

        if not configs.exists():
            self.stdout.write(self.style.WARNING('No PBX configurations found.'))
            return

        for config in configs:
            self.stdout.write(f"\nTesting connection to {config.name} ({config.host})...")
            client = YeastarClient(config)
            result = client.test_connection()

            if result['success']:
                self.stdout.write(self.style.SUCCESS(f"  {result['message']}"))
            else:
                self.stdout.write(self.style.ERROR(f"  {result['message']}"))

    def _sync_single_pbx(self, pbx_id, start_time, end_time, download, transcribe):
        """Sync a single PBX"""
        try:
            config = YeastarPBXConfig.objects.get(id=pbx_id)
        except YeastarPBXConfig.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'PBX configuration with ID {pbx_id} not found.'))
            return

        self.stdout.write(f"\nSyncing {config.name}...")
        self.stdout.write(f"  Time range: {start_time} to {end_time}")
        self.stdout.write(f"  Download recordings: {download}")
        self.stdout.write(f"  Transcribe: {transcribe}")

        service = SyncService(config)
        stats = service.sync_cdr(
            start_time=start_time,
            end_time=end_time,
            download_recordings=download,
            transcribe=transcribe
        )

        self._print_stats(stats)

    def _sync_all_pbx(self, start_time, end_time, download, transcribe):
        """Sync all active PBX configs"""
        configs = YeastarPBXConfig.objects.filter(is_active=True)

        if not configs.exists():
            self.stdout.write(self.style.WARNING('No active PBX configurations found.'))
            return

        self.stdout.write(f"\nSyncing {configs.count()} PBX system(s)...")
        self.stdout.write(f"  Time range: {start_time} to {end_time}")

        total_stats = {
            'cdr_fetched': 0,
            'cdr_new': 0,
            'recordings_downloaded': 0,
            'transcriptions_created': 0,
            'errors': []
        }

        for config in configs:
            self.stdout.write(f"\n  Syncing {config.name}...")
            service = SyncService(config)
            stats = service.sync_cdr(
                start_time=start_time,
                end_time=end_time,
                download_recordings=download,
                transcribe=transcribe
            )

            total_stats['cdr_fetched'] += stats['cdr_fetched']
            total_stats['cdr_new'] += stats['cdr_new']
            total_stats['recordings_downloaded'] += stats['recordings_downloaded']
            total_stats['transcriptions_created'] += stats['transcriptions_created']
            total_stats['errors'].extend(stats['errors'])

        self._print_stats(total_stats)

    def _print_stats(self, stats):
        """Print sync statistics"""
        self.stdout.write(self.style.SUCCESS('\nSync completed!'))
        self.stdout.write(f"  CDR records fetched: {stats['cdr_fetched']}")
        self.stdout.write(f"  New CDR records: {stats['cdr_new']}")
        self.stdout.write(f"  Recordings downloaded: {stats['recordings_downloaded']}")
        self.stdout.write(f"  Transcriptions created: {stats['transcriptions_created']}")

        if stats['errors']:
            self.stdout.write(self.style.WARNING(f"\n  Errors ({len(stats['errors'])}):"))
            for error in stats['errors'][:5]:
                self.stdout.write(f"    - {error}")
            if len(stats['errors']) > 5:
                self.stdout.write(f"    ... and {len(stats['errors']) - 5} more")
