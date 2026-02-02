"""
Yeastar PBX API Client for S-Series (including S70)

API Documentation: https://help.yeastar.com/en/s-series-developer/
"""

import hashlib
import logging
import requests
from datetime import datetime, timedelta
from typing import Optional
from django.utils import timezone

logger = logging.getLogger(__name__)


class YeastarAPIError(Exception):
    """Custom exception for Yeastar API errors"""
    pass


class YeastarClient:
    """Client for interacting with Yeastar S-Series PBX API"""

    def __init__(self, pbx_config):
        """
        Initialize the Yeastar API client.

        Args:
            pbx_config: YeastarPBXConfig model instance
        """
        self.config = pbx_config
        self.base_url = pbx_config.base_url
        self.api_version = pbx_config.api_version
        self.token = None
        self.token_expires_at = None
        self.session = requests.Session()
        self.session.verify = False  # Many PBX systems use self-signed certs

    def _get_api_url(self, endpoint: str) -> str:
        """Build full API URL"""
        return f"{self.base_url}/api/{self.api_version}/{endpoint}"

    def _md5_hash(self, text: str) -> str:
        """Create MD5 hash of text (lowercase)"""
        return hashlib.md5(text.encode()).hexdigest().lower()

    def _is_token_valid(self) -> bool:
        """Check if current token is still valid"""
        if not self.token or not self.token_expires_at:
            return False
        return timezone.now() < self.token_expires_at

    def login(self) -> bool:
        """
        Authenticate with the PBX and obtain an API token.

        Returns:
            bool: True if login successful
        """
        url = self._get_api_url('login')
        password_hash = self._md5_hash(self.config.password)

        payload = {
            'username': self.config.username,
            'password': password_hash
        }

        try:
            response = self.session.post(url, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()

            if data.get('status') == 'Success' or data.get('errcode') == 0:
                self.token = data.get('token')
                # Token expires in 30 minutes, refresh at 25 minutes
                self.token_expires_at = timezone.now() + timedelta(minutes=25)
                logger.info(f"Successfully logged in to PBX: {self.config.host}")
                return True
            else:
                error_msg = data.get('errmsg', 'Unknown error')
                logger.error(f"PBX login failed: {error_msg}")
                raise YeastarAPIError(f"Login failed: {error_msg}")

        except requests.RequestException as e:
            logger.error(f"PBX connection error: {e}")
            raise YeastarAPIError(f"Connection error: {e}")

    def ensure_token(self):
        """Ensure we have a valid token, login if needed"""
        if not self._is_token_valid():
            self.login()

    def logout(self):
        """Logout and invalidate the token"""
        if not self.token:
            return

        url = self._get_api_url('logout')
        try:
            self.session.post(
                f"{url}?token={self.token}",
                json={},
                timeout=10
            )
        except requests.RequestException:
            pass
        finally:
            self.token = None
            self.token_expires_at = None

    def heartbeat(self) -> bool:
        """
        Send heartbeat to keep token alive.

        Returns:
            bool: True if heartbeat successful
        """
        self.ensure_token()
        url = self._get_api_url('heartbeat')

        try:
            response = self.session.post(
                f"{url}?token={self.token}",
                json={},
                timeout=10
            )
            data = response.json()
            if data.get('status') == 'Success' or data.get('errcode') == 0:
                self.token_expires_at = timezone.now() + timedelta(minutes=25)
                return True
            return False
        except requests.RequestException:
            return False

    def get_cdr(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        caller: Optional[str] = None,
        callee: Optional[str] = None
    ) -> list:
        """
        Get Call Detail Records from PBX.

        Args:
            start_time: Filter by start time
            end_time: Filter by end time
            caller: Filter by caller number
            callee: Filter by callee number

        Returns:
            list: List of CDR records
        """
        self.ensure_token()

        # First get a random string for CDR download
        random_url = self._get_api_url('cdr/get_random')
        try:
            response = self.session.post(
                f"{random_url}?token={self.token}",
                json={},
                timeout=30
            )
            data = response.json()

            if data.get('status') != 'Success' and data.get('errcode') != 0:
                raise YeastarAPIError(f"Failed to get CDR random: {data.get('errmsg')}")

            random_string = data.get('random')

            # Now get the CDR data
            cdr_url = self._get_api_url('cdr/download')
            params = {
                'token': self.token,
                'random': random_string
            }

            if start_time:
                params['starttime'] = start_time.strftime('%Y-%m-%d %H:%M:%S')
            if end_time:
                params['endtime'] = end_time.strftime('%Y-%m-%d %H:%M:%S')
            if caller:
                params['caller'] = caller
            if callee:
                params['callee'] = callee

            response = self.session.get(cdr_url, params=params, timeout=60)

            # CDR is returned as CSV
            if response.headers.get('Content-Type', '').startswith('text/csv'):
                return self._parse_cdr_csv(response.text)
            else:
                # Try JSON response
                try:
                    data = response.json()
                    return data.get('cdr', [])
                except ValueError:
                    logger.error(f"Unexpected CDR response format")
                    return []

        except requests.RequestException as e:
            logger.error(f"CDR fetch error: {e}")
            raise YeastarAPIError(f"CDR fetch error: {e}")

    def _parse_cdr_csv(self, csv_content: str) -> list:
        """Parse CDR CSV content into list of dicts"""
        import csv
        from io import StringIO

        records = []
        reader = csv.DictReader(StringIO(csv_content))

        for row in reader:
            records.append({
                'id': row.get('id', ''),
                'time': row.get('time', ''),
                'caller': row.get('src', row.get('caller', '')),
                'callee': row.get('dst', row.get('callee', '')),
                'call_from': row.get('callfrom', ''),
                'call_to': row.get('callto', ''),
                'duration': int(row.get('duration', 0) or 0),
                'talk_duration': int(row.get('talkdur', row.get('billsec', 0)) or 0),
                'status': row.get('disposition', row.get('status', '')),
                'recording': row.get('recording', row.get('recordfile', '')),
                'call_type': row.get('calltype', row.get('type', '')),
            })

        return records

    def get_recording_download_url(self, recording_filename: str) -> str:
        """
        Get download URL for a recording file.

        Args:
            recording_filename: Name of the recording file

        Returns:
            str: Download URL for the recording
        """
        self.ensure_token()

        # Get random string for recording download
        random_url = self._get_api_url('recording/get_random')

        try:
            response = self.session.post(
                f"{random_url}?token={self.token}",
                json={'recording': recording_filename},
                timeout=30
            )
            data = response.json()

            if data.get('status') != 'Success' and data.get('errcode') != 0:
                raise YeastarAPIError(f"Failed to get recording random: {data.get('errmsg')}")

            random_string = data.get('random')

            # Build download URL
            download_url = self._get_api_url('recording/download')
            return f"{download_url}?recording={recording_filename}&random={random_string}&token={self.token}"

        except requests.RequestException as e:
            logger.error(f"Recording URL error: {e}")
            raise YeastarAPIError(f"Recording URL error: {e}")

    def download_recording(self, recording_filename: str) -> bytes:
        """
        Download a recording file from the PBX.

        Args:
            recording_filename: Name of the recording file

        Returns:
            bytes: Recording file content
        """
        download_url = self.get_recording_download_url(recording_filename)

        try:
            response = self.session.get(download_url, timeout=300, stream=True)
            response.raise_for_status()

            # Check if we got an actual file
            content_type = response.headers.get('Content-Type', '')
            if 'audio' in content_type or 'octet-stream' in content_type:
                return response.content
            else:
                # Might be an error response
                try:
                    data = response.json()
                    raise YeastarAPIError(f"Download failed: {data.get('errmsg', 'Unknown error')}")
                except ValueError:
                    return response.content

        except requests.RequestException as e:
            logger.error(f"Recording download error: {e}")
            raise YeastarAPIError(f"Recording download error: {e}")

    def test_connection(self) -> dict:
        """
        Test connection to PBX.

        Returns:
            dict: Connection test result with status and message
        """
        try:
            self.login()
            self.logout()
            return {
                'success': True,
                'message': 'Successfully connected to PBX'
            }
        except YeastarAPIError as e:
            return {
                'success': False,
                'message': str(e)
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Connection error: {e}'
            }


def get_client(pbx_config) -> YeastarClient:
    """Factory function to create a YeastarClient instance"""
    return YeastarClient(pbx_config)
