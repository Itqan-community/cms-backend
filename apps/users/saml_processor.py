from djangosaml2idp.processors import BaseProcessor


class MixpanelSAMLProcessor(BaseProcessor):
    def has_access(self, request) -> bool:
        user = request.user
        if not (user and user.is_authenticated and user.is_active):
            return False
        return user.publisher_memberships.exists()

    def get_user_id(self, user) -> str:
        return user.email
