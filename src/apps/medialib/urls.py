"""
URL configuration for Media Library API
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'medialib'

# Create router for API endpoints
router = DefaultRouter()
router.register(r'folders', views.MediaFolderViewSet, basename='folder')
router.register(r'files', views.MediaFileViewSet, basename='file')
router.register(r'attachments', views.MediaAttachmentViewSet, basename='attachment')

urlpatterns = [
    path('api/v1/media/', include(router.urls)),
]
