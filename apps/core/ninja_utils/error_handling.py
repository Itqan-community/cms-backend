import logging
from json import JSONDecodeError

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
from django.utils.encoding import force_str
from django.utils.translation import gettext as _
from ninja.errors import AuthenticationError, HttpError
from ninja.errors import ValidationError as NinjaValidationError
from rest_framework.exceptions import PermissionDenied
from rest_framework.serializers import as_serializer_error
from rest_framework_simplejwt.exceptions import AuthenticationFailed, InvalidToken

from apps.core.ninja_utils.errors import ItqanError, NinjaErrorResponse
from config.ninja_urls import ninja_api

"""
Unify Error Responses from Django Ninja into a standard format.
"""


@ninja_api.exception_handler(PermissionDenied)
def handle_permission_denied(request, exc: PermissionDenied):
    return ninja_api.create_response(
        request, NinjaErrorResponse(error_name="permission_denied", message=exc.detail), status=403
    )


@ninja_api.exception_handler(ItqanError)
def handle_itqan_error(request, exc: ItqanError):
    return ninja_api.create_response(
        request,
        NinjaErrorResponse(error_name=exc.error_name, message=exc.message, extra=exc.extra),
        status=exc.status_code,
    )


@ninja_api.exception_handler(NinjaValidationError)
def handle_ninja_validation_error(request, exc: NinjaValidationError):
    return ninja_api.create_response(
        request,
        NinjaErrorResponse(
            error_name="validation_error", message=_("Invalid Input"), extra=exc.errors
        ),
        status=400,
    )


@ninja_api.exception_handler(DjangoValidationError)
def handle_django_validation_error(request, exc: DjangoValidationError):
    error: dict[str, list] = as_serializer_error(exc)
    return ninja_api.create_response(
        request,
        NinjaErrorResponse(
            error_name="validation_error",
            message=_("Invalid Input"),
            extra=error["non_field_errors"],
        ),
        status=400,
    )


@ninja_api.exception_handler(Http404)
def handle_django_404(request, exc: Http404):
    return ninja_api.create_response(
        request, NinjaErrorResponse(error_name="not_found", message=exc.args[0]), status=404
    )


@ninja_api.exception_handler(AuthenticationError)
def handle_ninja_authentication_error(request, exc: AuthenticationError):
    return ninja_api.create_response(
        request,
        NinjaErrorResponse(
            error_name="authentication_error", message=exc.message or _("Authentication Error")
        ),
        status=401,
    )


@ninja_api.exception_handler(InvalidToken)
def handle_ninja_authentication_error(request, exc: InvalidToken):
    return ninja_api.create_response(
        request,
        NinjaErrorResponse(error_name="token_not_valid", message=force_str(exc.default_detail)),
        status=401,
    )


@ninja_api.exception_handler(AuthenticationFailed)
def handle_ninja_authentication_error(request, exc: AuthenticationFailed):
    return ninja_api.create_response(
        request,
        NinjaErrorResponse(error_name="token_not_valid", message=force_str(exc.default_detail)),
        status=401,
    )


@ninja_api.exception_handler(HttpError)
def handle_ninja_http_error(request, exc: HttpError):
    # ninja throws HttpError with `__cause__`
    # we should return this error to the user in our standard format
    # if one of Itqan developers uses HttpError they should be directed to use ItqanError instead
    cause = getattr(exc, "__cause__", None)
    if cause is None:
        raise AttributeError(f"Use ItqanError instead of {exc}")

    if isinstance(cause, JSONDecodeError):
        return ninja_api.create_response(
            request,
            NinjaErrorResponse(error_name="invalid_json", message=str(exc)),
            status=400,
        )

    else:
        return ninja_api.create_response(
            request,
            NinjaErrorResponse(error_name="http_error", message=exc.message),
            status=exc.status_code,
        )


@ninja_api.exception_handler(Exception)
def handle_generic_exception(request, exc: Exception):
    if settings.DEBUG or (request.user and getattr(request.user, "is_superuser", False)):
        # let it propagate to be handled by django, and show detailed error page
        raise exc
    logger = logging.getLogger(__name__)
    logger.error("Unhandled exception", exc_info=exc)
    # in production
    return ninja_api.create_response(
        request,
        NinjaErrorResponse(
            error_name="internal_error", message=_("Something went wrong - Internal Server Error")
        ),
        status=500,
    )
