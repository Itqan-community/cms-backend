"""
URL configuration for Authentication API
"""
from django.urls import path
from . import views

app_name = 'authentication'

urlpatterns = [
    # Auth0 authentication endpoints
    path('login/', views.Auth0LoginView.as_view(), name='auth0_login'),
    path('exchange/', views.TokenExchangeView.as_view(), name='token_exchange'),
    path('validate/', views.validate_token, name='validate_token'),
    path('profile/', views.user_profile, name='user_profile'),
    
    # Configuration and health endpoints  
    path('config/', views.auth0_config, name='auth0_config'),
    path('health/', views.auth0_health, name='auth0_health'),
]
