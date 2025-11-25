from django import forms

from apps.content.models import Asset


class DownloadRecitationsJsonForm(forms.Form):
    asset = forms.ModelChoiceField(
        queryset=Asset.objects.filter(category="recitation"),
        label="Asset (mushaf)",
        help_text="Select the recitation asset to generate its tracks JSON file",
    )
