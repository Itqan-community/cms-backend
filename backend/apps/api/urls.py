"""
API URL Configuration
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

# API Router
router = DefaultRouter()

# For now, we'll create basic placeholder endpoints
# These will be expanded in Task 4: Django REST API v1

urlpatterns = [
    path('', include(router.urls)),
    # path('content/', include('apps.content.api.urls')),
    # path('licensing/', include('apps.licensing.api.urls')),
    # path('analytics/', include('apps.analytics.api.urls')),
]
