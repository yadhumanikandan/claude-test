from django import forms
from .models import Transcription, YeastarPBXConfig


class AudioUploadForm(forms.ModelForm):
    class Meta:
        model = Transcription
        fields = ['audio_file']
        widgets = {
            'audio_file': forms.FileInput(attrs={
                'accept': 'audio/*,.mp3,.wav,.m4a,.ogg,.flac,.webm',
                'class': 'form-control'
            })
        }

    def clean_audio_file(self):
        audio_file = self.cleaned_data.get('audio_file')
        if audio_file:
            valid_extensions = ['.mp3', '.wav', '.m4a', '.ogg', '.flac', '.webm', '.mp4', '.mpeg']
            ext = audio_file.name.lower().split('.')[-1]
            if f'.{ext}' not in valid_extensions:
                raise forms.ValidationError(
                    f'Unsupported file format. Please upload one of: {", ".join(valid_extensions)}'
                )
            if audio_file.size > 100 * 1024 * 1024:  # 100MB limit
                raise forms.ValidationError('File size must be less than 100MB')
        return audio_file


class YeastarPBXConfigForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        help_text='API password (will be stored securely)'
    )

    class Meta:
        model = YeastarPBXConfig
        fields = [
            'name', 'host', 'port', 'use_https', 'username', 'password',
            'api_version', 'is_active', 'auto_sync', 'sync_interval_minutes'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'My PBX'}),
            'host': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '192.168.1.100'}),
            'port': forms.NumberInput(attrs={'class': 'form-control'}),
            'use_https': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'api'}),
            'api_version': forms.Select(
                choices=[('v1.1.0', 'v1.1.0'), ('v2.0.0', 'v2.0.0')],
                attrs={'class': 'form-control'}
            ),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'auto_sync': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'sync_interval_minutes': forms.NumberInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # If editing existing config, don't require password
        if self.instance and self.instance.pk:
            self.fields['password'].required = False
            self.fields['password'].help_text = 'Leave blank to keep current password'

    def clean_password(self):
        password = self.cleaned_data.get('password')
        # If editing and password is blank, keep the old one
        if not password and self.instance and self.instance.pk:
            return self.instance.password
        return password
