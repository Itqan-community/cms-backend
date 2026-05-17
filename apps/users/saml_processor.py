from djangosaml2idp.idp import IDP
from djangosaml2idp.processors import BaseProcessor

from apps.users.models import User


class SamlIdpReloadMiddleware:
    """Force IDP metadata reload on each SAML request.

    Gunicorn forks multiple workers that each cache IDP._server_instance in memory.
    When an SP is registered or updated, only the worker that processed the save()
    gets a refreshed instance. This middleware ensures all workers reload from DB.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith("/idp/"):
            IDP._server_instance = None
        return self.get_response(request)


class MixpanelSAMLProcessor(BaseProcessor):
    def has_access(self, request) -> bool:
        user = request.user
        if not (user and user.is_authenticated and user.is_active):
            return False
        return user.publisher_memberships.exists()

    def create_identity(self, user: User, sp_attribute_mapping: dict[str, str]) -> dict[str, str]:
        display_name = (user.name or user.email.split("@")[0]).strip()
        return {
            "email": user.email,
            "firstName": display_name,
            "lastName": display_name,
            "username": user.email,
        }
