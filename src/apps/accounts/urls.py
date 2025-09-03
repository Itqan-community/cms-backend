"""
Accounts URL Configuration (Authentication)
Implements the API contract authentication endpoints
"""
from django.urls import path, include
from . import auth_views

app_name = 'accounts'

urlpatterns = [
    # API Contract Authentication Endpoints - EXACT paths as per contract
    # 1.1) Register with Email/Password - /auth/register
    path('register/', auth_views.RegisterView.as_view(), name='auth_register'),
    
    # 1.2) Login with Email/Password - /auth/login  
    path('login/', auth_views.LoginView.as_view(), name='auth_login'),
    
    # 1.3) OAuth2 - Google/GitHub Login - /auth/oauth/google/start, /auth/oauth/github/start
    path('oauth/google/start/', auth_views.OAuthStartView.as_view(), {'provider': 'google'}, name='oauth_google_start'),
    path('oauth/github/start/', auth_views.OAuthStartView.as_view(), {'provider': 'github'}, name='oauth_github_start'),
    
    # 1.3) OAuth2 - Google/GitHub Callback - /auth/oauth/google/callback, /auth/oauth/github/callback
    path('oauth/google/callback/', auth_views.OAuthCallbackView.as_view(), {'provider': 'google'}, name='oauth_google_callback'),
    path('oauth/github/callback/', auth_views.OAuthCallbackView.as_view(), {'provider': 'github'}, name='oauth_github_callback'),
    
    # 1.4) Get User Profile & 1.5) Update User Profile - /auth/profile
    path('profile/', auth_views.UserProfileView.as_view(), name='auth_profile'),
    
    # 1.6) Refresh Token - /auth/token/refresh
    path('token/refresh/', auth_views.TokenRefreshView.as_view(), name='token_refresh'),
    
    # 1.7) Logout - /auth/logout
    path('logout/', auth_views.LogoutView.as_view(), name='auth_logout'),
    
    # Include allauth URLs for OAuth handling (under different path)
    path('_allauth/', include('allauth.socialaccount.urls')),
]
