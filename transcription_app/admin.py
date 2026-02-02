from django.contrib import admin
from django.utils.html import format_html
from .models import YeastarPBXConfig, CDRRecord, Transcription


@admin.register(YeastarPBXConfig)
class YeastarPBXConfigAdmin(admin.ModelAdmin):
    list_display = ['name', 'host', 'port', 'is_active', 'auto_sync', 'last_sync_at']
    list_filter = ['is_active', 'auto_sync']
    search_fields = ['name', 'host']
    readonly_fields = ['last_sync_at', 'created_at', 'updated_at']
    fieldsets = (
        ('Connection', {
            'fields': ('name', 'host', 'port', 'use_https', 'api_version')
        }),
        ('Authentication', {
            'fields': ('username', 'password'),
            'description': 'API credentials for the PBX'
        }),
        ('Sync Settings', {
            'fields': ('is_active', 'auto_sync', 'sync_interval_minutes')
        }),
        ('Info', {
            'fields': ('last_sync_at', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(CDRRecord)
class CDRRecordAdmin(admin.ModelAdmin):
    list_display = ['call_id', 'caller', 'callee', 'duration_display', 'call_time', 'has_recording', 'has_transcription']
    list_filter = ['pbx_config', 'call_type', 'status']
    search_fields = ['caller', 'callee', 'call_id']
    readonly_fields = ['call_id', 'raw_data', 'created_at']
    date_hierarchy = 'call_time'

    def duration_display(self, obj):
        minutes, seconds = divmod(obj.duration, 60)
        return f"{minutes}m {seconds}s"
    duration_display.short_description = 'Duration'

    def has_recording(self, obj):
        return bool(obj.recording_file)
    has_recording.boolean = True
    has_recording.short_description = 'Recording'

    def has_transcription(self, obj):
        return hasattr(obj, 'transcription') and obj.transcription is not None
    has_transcription.boolean = True
    has_transcription.short_description = 'Transcribed'


@admin.register(Transcription)
class TranscriptionAdmin(admin.ModelAdmin):
    list_display = ['original_filename', 'source', 'status_badge', 'call_info', 'created_at']
    list_filter = ['status', 'source']
    search_fields = ['original_filename', 'transcript']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'created_at'

    def status_badge(self, obj):
        colors = {
            'pending': '#6b7280',
            'downloading': '#f59e0b',
            'processing': '#3b82f6',
            'completed': '#10b981',
            'failed': '#ef4444',
        }
        color = colors.get(obj.status, '#6b7280')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 4px; font-size: 11px;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'

    def call_info(self, obj):
        if obj.cdr_record:
            return f"{obj.cdr_record.caller} → {obj.cdr_record.callee}"
        return '-'
    call_info.short_description = 'Call'
