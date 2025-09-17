from ninja import Schema


class ItqanError(Exception):
    def __init__(self, error_name: str, message: str, status_code: int = 400, extra=None):
        """
        error_name: is a unique name for the error should not contain spaces
        message: is a human-readable message, this should be localized
        """
        assert " " not in error_name

        self.error_name = error_name
        self.message = str(message)
        self.status_code = status_code
        self.extra = extra or {}


class NinjaErrorResponse[ERROR_NAME, EXTRA_TYPE](Schema):
    error_name: ERROR_NAME
    message: str
    extra: EXTRA_TYPE | None = None
