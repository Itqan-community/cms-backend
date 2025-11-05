"""
Django Allauth custom forms
"""

from allauth.account.forms import SignupForm
from allauth.socialaccount.forms import SignupForm as SocialSignupForm
from django import forms


class UserSignupForm(SignupForm):
    """
    Custom signup form for regular registration
    """

    name = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Full Name"}),
    )

    def save(self, request):
        user = super().save(request)
        user.name = self.cleaned_data.get("name", "")
        user.save()
        return user


class UserSocialSignupForm(SocialSignupForm):
    """
    Custom social signup form for OAuth registration
    """

    name = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Full Name"}),
    )

    def save(self, request):
        user = super().save(request)
        if self.cleaned_data.get("name"):
            user.name = self.cleaned_data["name"]
            user.save()
        return user
