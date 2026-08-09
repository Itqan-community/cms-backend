from django import forms
from django.utils.translation import gettext_lazy as _


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


class RecitationAyahTimestampsBulkUploadForm(forms.Form):
    json_files = MultipleFileField(
        label="JSON Files",
        help_text="Upload one or multiple .json files (one per surah)",
    )

    def clean_json_files(self):
        files = self.files.getlist("json_files")
        if not files:
            raise forms.ValidationError(_("Please select at least one file."))
        invalid = [f.name for f in files if not f.name.lower().endswith(".json")]
        if invalid:
            raise forms.ValidationError(
                _("All files must have .json extension. Invalid: {invalid}").format(invalid=", ".join(invalid[:5]))
            )
        return files
