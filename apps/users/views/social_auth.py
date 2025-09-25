import secrets
from django.http import HttpRequest, HttpResponseRedirect
from django.urls import reverse
from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from allauth.socialaccount.providers.github.views import GitHubOAuth2Adapter
from allauth.socialaccount.models import SocialApp
from allauth.socialaccount.providers.oauth2.client import OAuth2Client

from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.errors import ItqanError
from apps.core.ninja_utils.tags import NinjaTag
from ._schemas import OAuth2AuthorizeResponseSchema
from apps.core.ninja_utils.request import Request

router = ItqanRouter(tags=[NinjaTag.SOCIAL_AUTH])


@router.get(
    "auth/oauth/google/authorize/",
auth=None,
    response=OAuth2AuthorizeResponseSchema,
    summary="Start Google OAuth2 authorization",
    description="Redirect user to Google OAuth2 authorization page"
)
def google_oauth_authorize(request: Request):
    """Start Google OAuth2 authorization flow"""
    try:
        # Get Google social app configuration
        google_app = SocialApp.objects.get(provider='google')
    except SocialApp.DoesNotExist:
        raise ItqanError(
            error_name="google_app_not_configured",
            message="Google OAuth2 application is not configured",
            status_code=500
        )
    
    try:
        # Create OAuth2 client
        adapter = GoogleOAuth2Adapter(request)
        client = OAuth2Client(
            client_id=google_app.client_id,
            client_secret=google_app.secret,
        )
        
        # Generate authorization URL
        callback_url = request.build_absolute_uri(reverse('google_oauth_callback'))
        auth_url = adapter.get_provider().get_auth_url(
            request, 
            callback_url,
            client=client
        )
        
        # Generate state for security
        state = secrets.token_urlsafe(32)
        request.session['oauth_state'] = state
        
        return {
            "authorization_url": f"{auth_url}&state={state}",
            "state": state
        }
    except Exception as e:
        raise ItqanError(
            error_name="google_oauth_setup_failed",
            message=f"Failed to generate Google authorization URL: {str(e)}",
            status_code=500
        )


@router.get(
    "auth/oauth/github/authorize/",
auth=None,
    response=OAuth2AuthorizeResponseSchema,
    summary="Start GitHub OAuth2 authorization",
    description="Redirect user to GitHub OAuth2 authorization page"
)
def github_oauth_authorize(request: Request):
    """Start GitHub OAuth2 authorization flow"""
    try:
        # Get GitHub social app configuration
        github_app = SocialApp.objects.get(provider='github')
    except SocialApp.DoesNotExist:
        raise ItqanError(
            error_name="github_app_not_configured",
            message="GitHub OAuth2 application is not configured",
            status_code=500
        )
    
    try:
        # Generate state for security
        state = secrets.token_urlsafe(32)
        request.session['oauth_state'] = state
        
        # Build GitHub OAuth URL
        callback_url = request.build_absolute_uri('/auth/oauth/github/callback/')
        auth_url = (
            f"https://github.com/login/oauth/authorize"
            f"?client_id={github_app.client_id}"
            f"&redirect_uri={callback_url}"
            f"&scope=user:email"
            f"&state={state}"
        )
        
        return {
            "authorization_url": auth_url,
            "state": state
        }
    except Exception as e:
        raise ItqanError(
            error_name="github_oauth_setup_failed",
            message=f"Failed to generate GitHub authorization URL: {str(e)}",
            status_code=500
        )


@router.get(
    "auth/oauth/google/callback/",
auth=None,
    summary="Google OAuth2 callback redirect",
    description="Redirects to allauth Google callback for processing"
)
def google_oauth_callback(request: Request):
    """Redirect to allauth Google callback"""
    return HttpResponseRedirect('/accounts/google/login/callback/')


@router.get(
    "auth/oauth/github/callback/",
auth=None,
    summary="GitHub OAuth2 callback redirect", 
    description="Redirects to allauth GitHub callback for processing"
)
def github_oauth_callback(request: Request):
    """Redirect to allauth GitHub callback"""
    return HttpResponseRedirect('/accounts/github/login/callback/')
