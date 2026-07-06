from __future__ import annotations

from allauth.account import app_settings
from allauth.account.adapter import DefaultAccountAdapter
from allauth.core import context as allauth_context
from allauth.mfa.adapter import DefaultMFAAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.socialaccount.models import SocialLogin
from django.conf import settings
from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.template import TemplateDoesNotExist
from django.template.loader import render_to_string
from django.utils.translation import gettext_lazy as _


class AccountAdapter(DefaultAccountAdapter):
    """
    Custom account adapter for handling user registration
    """

    def send_mail(self, template_prefix, email, context):
        # Inject a translatable site name so emails render the brand in the
        # recipient's language (allauth activates it before sending) instead of
        # the non-translatable Site.name from the database.
        context.setdefault("site_name", _("Itqan Community"))
        return super().send_mail(template_prefix, email, context)

    def render_mail(self, template_prefix, email, context, headers=None):
        # allauth hardcodes _subject.txt; we override to use .html subject templates
        to = [email] if isinstance(email, str) else email
        html_ext = app_settings.TEMPLATE_EXTENSION
        subject = render_to_string(f"{template_prefix}_subject.{html_ext}", context)
        subject = " ".join(subject.splitlines()).strip()
        subject = self.format_email_subject(subject)

        from_email = self.get_from_email()
        bodies = {}
        for ext in [html_ext, "txt"]:
            try:
                bodies[ext] = render_to_string(
                    f"{template_prefix}_message.{ext}",
                    context,
                    allauth_context.request,
                ).strip()
            except TemplateDoesNotExist:
                if ext == "txt" and not bodies:
                    raise

        if "txt" in bodies:
            msg = EmailMultiAlternatives(subject, bodies["txt"], from_email, to, headers=headers)
            if html_ext in bodies:
                msg.attach_alternative(bodies[html_ext], "text/html")
        else:
            msg = EmailMessage(subject, bodies[html_ext], from_email, to, headers=headers)
            msg.content_subtype = "html"
        return msg

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
