"""
Core app URL configuration
"""

from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('health/', views.health_check, name='health'),
    path('auth/me/', views.AuthMeView.as_view(), name='auth_me'),
    path('auth/complete-profile/', views.CompleteProfileView.as_view(), name='complete_profile'),
    path('auth/callback/', views.AuthCallbackView.as_view(), name='auth_callback'),
]
