from __future__ import annotations

from allauth.account.adapter import DefaultAccountAdapter
from allauth.mfa.adapter import DefaultMFAAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.socialaccount.models import SocialLogin
from django.conf import settings


class AccountAdapter(DefaultAccountAdapter):
    """
    Custom account adapter for handling user registration
    """

    def is_open_for_signup(self, request):
        """
        Allow user registration
        """
        return True

    def save_user(self, request, user, form, commit=True):
        """
        Save user with custom fields
        """

        # Set additional fields if needed
        if hasattr(form, "cleaned_data"):
            user.name = form.cleaned_data.get("name", "")

        if commit:
            user.save()

        return user


class SocialAccountAdapter(DefaultSocialAccountAdapter):

    def populate_user(self, request, sociallogin: SocialLogin, common_fields):
        """
        Populate user from social account data
        """
        user = super().populate_user(request, sociallogin, common_fields)
        # Set additional fields based on provider
        if sociallogin.account.provider == "google":
            user.name = sociallogin.account.extra_data.get("name", "").strip()

        elif sociallogin.account.provider == "github":
            extra_data = sociallogin.account.extra_data
            user.name = common_fields.get("name") or common_fields.get("username") or extra_data.get("login", "")
        if sociallogin.is_existing:
            user.save()
        return user


class MFAAdapter(DefaultMFAAdapter):
    """
    Custom MFA adapter to control WebAuthn Relying Party (RP) entity.

    Default allauth uses request host (often API domain), which can cause
    passkey RP mismatch when FE runs on another subdomain.
    """

    def get_public_key_credential_rp_entity(self) -> dict[str, str]:
        return {
            "id": settings.WEBAUTHN_RP_ID,
            "name": self._get_site_name(),
        }
