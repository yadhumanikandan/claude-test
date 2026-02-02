from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
import os


def audio_upload_path(instance, filename):
    return os.path.join('uploads', 'audio', filename)


class YeastarPBXConfig(models.Model):
    """Configuration for Yeastar PBX connection"""
    name = models.CharField(max_length=100, default='Default PBX')
    host = models.CharField(max_length=255, help_text='PBX IP address or hostname')
    port = models.IntegerField(
        default=8088,
        validators=[MinValueValidator(1), MaxValueValidator(65535)],
        help_text='API port (default: 8088 for HTTPS)'
    )
    use_https = models.BooleanField(default=True, help_text='Use HTTPS for API calls')
    username = models.CharField(max_length=100, help_text='API username')
    password = models.CharField(max_length=100, help_text='API password (will be MD5 hashed)')
    api_version = models.CharField(
        max_length=20,
        default='v2.0.0',
        help_text='API version (v1.1.0 or v2.0.0)'
    )
    is_active = models.BooleanField(default=True)
    auto_sync = models.BooleanField(
        default=False,
        help_text='Automatically sync new recordings'
    )
    sync_interval_minutes = models.IntegerField(
        default=5,
        validators=[MinValueValidator(1)],
        help_text='How often to check for new recordings (minutes)'
    )
    last_sync_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Yeastar PBX Configuration'
        verbose_name_plural = 'Yeastar PBX Configurations'

    def __str__(self):
        return f"{self.name} ({self.host})"

    @property
    def base_url(self):
        protocol = 'https' if self.use_https else 'http'
        return f"{protocol}://{self.host}:{self.port}"


class CDRRecord(models.Model):
    """Call Detail Record from Yeastar PBX"""
    pbx_config = models.ForeignKey(
        YeastarPBXConfig,
        on_delete=models.CASCADE,
        related_name='cdr_records'
    )
    call_id = models.CharField(max_length=100, unique=True)
    caller = models.CharField(max_length=100)
    callee = models.CharField(max_length=100)
    call_from = models.CharField(max_length=100, blank=True)
    call_to = models.CharField(max_length=100, blank=True)
    duration = models.IntegerField(default=0, help_text='Call duration in seconds')
    talk_duration = models.IntegerField(default=0, help_text='Talk duration in seconds')
    call_type = models.CharField(max_length=50, blank=True)
    status = models.CharField(max_length=50, blank=True)
    recording_file = models.CharField(max_length=500, blank=True, help_text='Recording filename on PBX')
    call_time = models.DateTimeField(null=True, blank=True)
    raw_data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-call_time']
        verbose_name = 'CDR Record'
        verbose_name_plural = 'CDR Records'

    def __str__(self):
        return f"{self.caller} -> {self.callee} ({self.call_time})"


class Transcription(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('downloading', 'Downloading'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    SOURCE_CHOICES = [
        ('upload', 'Manual Upload'),
        ('yeastar', 'Yeastar PBX'),
    ]

    audio_file = models.FileField(upload_to=audio_upload_path)
    original_filename = models.CharField(max_length=255)
    transcript = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    error_message = models.TextField(blank=True, null=True)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='upload')
    cdr_record = models.OneToOneField(
        CDRRecord,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transcription'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.original_filename} - {self.status}"

    @property
    def caller(self):
        return self.cdr_record.caller if self.cdr_record else None

    @property
    def callee(self):
        return self.cdr_record.callee if self.cdr_record else None

    @property
    def call_duration(self):
        return self.cdr_record.duration if self.cdr_record else None
