from django import forms


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list | tuple)):
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = [single_file_clean(data, initial)]
        return result


class BulkRecitationUploadForm(forms.Form):
    audio_files = MultipleFileField(
        label="Audio Files",
        help_text="Upload one or multiple recitation .mp3 files",
    )

    def clean_audio_files(self):
        files = self.files.getlist("audio_files")
        if not files:
            raise forms.ValidationError("Please select at least one file.")
        return files
