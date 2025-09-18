from django.urls import URLPattern
from django.urls import include
from django.urls import path

from apps.users import views

app_name = "users"

urlpatterns: list[URLPattern] = [
    # 1.1) Register with Email/Password - /auth/register
    path("register/", views.RegisterView.as_view(), name="auth_register"),
    # 1.2) Login with Email/Password - /auth/login
    path("login/", views.LoginView.as_view(), name="auth_login"),
    # 1.3) OAuth2 - Google/GitHub Login - /auth/oauth/google/start, /auth/oauth/github/start
    path("oauth/google/start/", views.OAuthStartView.as_view(), {"provider": "google"}, name="oauth_google_start"),
    path("oauth/github/start/", views.OAuthStartView.as_view(), {"provider": "github"}, name="oauth_github_start"),
    # 1.3) OAuth2 - Google/GitHub Callback - /auth/oauth/google/callback, /auth/oauth/github/callback
    path(
        "oauth/google/callback/",
        views.OAuthCallbackView.as_view(),
        {"provider": "google"},
        name="oauth_google_callback",
    ),
    path(
        "oauth/github/callback/",
        views.OAuthCallbackView.as_view(),
        {"provider": "github"},
        name="oauth_github_callback",
    ),
    # 1.4) Get User Profile & 1.5) Update User Profile - /auth/profile
    path("profile/", views.UserProfileView.as_view(), name="auth_profile"),
    # 1.7) Logout - /auth/logout
    path("logout/", views.LogoutView.as_view(), name="auth_logout"),
    # Include allauth URLs for OAuth handling (under different path)
    path("_allauth/", include("allauth.socialaccount.urls")),
]
