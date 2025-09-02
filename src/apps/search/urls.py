"""
URL configuration for Search API
"""
from django.urls import path
from . import views

app_name = 'search'

urlpatterns = [
    # Main search endpoint
    path('', views.SearchAPIView.as_view(), name='search'),
    
    # Search suggestions/autocomplete
    path('suggestions/', views.search_suggestions, name='suggestions'),
    
    # Admin management endpoints
    path('admin/rebuild/', views.rebuild_indexes, name='rebuild_indexes'),
    path('admin/reindex/', views.bulk_reindex, name='bulk_reindex'),
    path('admin/health/', views.search_health, name='search_health'),
    path('admin/stats/', views.search_stats, name='search_stats'),
]
