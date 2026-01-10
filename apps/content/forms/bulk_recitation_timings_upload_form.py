from django import forms

from apps.content.models import Asset


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


class BulkRecitationTimingsUploadForm(forms.Form):
    asset = forms.ModelChoiceField(
        queryset=Asset.objects.filter(category="recitation"),
        label="Asset (Mushaf)",
    )
    json_files = MultipleFileField(
        label="JSON Files",
        help_text="Upload one or multiple .json files (one per surah)",
    )
    overwrite = forms.BooleanField(
        required=False,
        initial=False,
        label="Overwrite existing timings",
        help_text="If enabled, existing timings will be updated when different.",
    )
    dry_run = forms.BooleanField(
        required=False,
        initial=True,
        label="Dry run (no database writes)",
        help_text="Validates and shows a summary without saving any changes.",
    )

    def clean_json_files(self):
        files = self.files.getlist("json_files")
        if not files:
            raise forms.ValidationError("Please select at least one file.")
        invalid = [f.name for f in files if not f.name.lower().endswith(".json")]
        if invalid:
            raise forms.ValidationError(f"All files must have .json extension. Invalid: {', '.join(invalid[:5])}")
        return files
