from django import forms
from .models import Transcription


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
