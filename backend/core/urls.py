"""
Core app URL configuration
"""

from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    # System endpoints
    path('', views.api_info, name='api_info'),
    path('health/', views.health_check, name='health'),
    
    # Authentication endpoints
    path('auth/me/', views.AuthMeView.as_view(), name='auth_me'),
    path('auth/complete-profile/', views.CompleteProfileView.as_view(), name='complete_profile'),
    path('auth/callback/', views.AuthCallbackView.as_view(), name='auth_callback'),
    path('auth/register/', views.RegisterView.as_view(), name='register'),
    path('auth/login/', views.LoginView.as_view(), name='login'),
]
