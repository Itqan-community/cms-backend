from __future__ import annotations

from apps.users.models import User


class UserRepository:
    def get_preferred_languages(self, emails: list[str]) -> dict[str, str]:
        """Map each (lowercased) email that belongs to a user to that user's preferred language."""
        return dict(
            User.objects.filter(email__in=[email.lower() for email in emails]).values_list(
                "email", "preferred_language"
            )
        )
