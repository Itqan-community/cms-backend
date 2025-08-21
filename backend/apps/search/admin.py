"""
Search Configuration Admin Interface for Itqan CMS
"""
from django.contrib import admin, messages
from django.shortcuts import render, redirect
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.conf import settings
from django.db import models

from .client import meili_client
from apps.content.models import Resource
from apps.accounts.models import User
from apps.medialib.models import MediaFile


class SearchConfigurationAdmin(admin.ModelAdmin):
    """
    Admin interface for managing MeiliSearch configuration and indexing
    """
    
    def get_urls(self):
        """Add custom admin URLs for search management"""
        urls = super().get_urls()
        custom_urls = [
            path('configuration/', self.admin_site.admin_view(self.configuration_view), name='search_configuration'),
            path('reindex/<str:index_name>/', self.admin_site.admin_view(self.reindex_view), name='search_reindex'),
            path('clear/<str:index_name>/', self.admin_site.admin_view(self.clear_view), name='search_clear'),
            path('health/', self.admin_site.admin_view(self.health_view), name='search_health'),
        ]
        return custom_urls + urls
    
    def configuration_view(self, request):
        """Main search configuration view"""
        context = self.get_search_status()
        context.update({
            'title': 'Search Configuration',
            'opts': self.model._meta,
            'app_label': 'search',
        })
        return render(request, 'admin/search/configuration.html', context)
    
    def health_view(self, request):
        """Check MeiliSearch health"""
        try:
            health = meili_client.health_check()
            if health:
                messages.success(request, 'MeiliSearch is healthy and accessible')
            else:
                messages.error(request, 'MeiliSearch is not responding')
        except Exception as e:
            messages.error(request, f'MeiliSearch health check failed: {e}')
        
        return redirect('admin:search_configuration')
    
    def reindex_view(self, request, index_name):
        """Reindex all documents for a specific index"""
        try:
            # Clear existing index
            meili_client.clear_index(index_name)
            
            # Reindex based on index type
            if index_name == 'resources':
                count = self.reindex_resources()
                messages.success(request, f'Successfully reindexed {count} resources')
            elif index_name == 'users':
                count = self.reindex_users()
                messages.success(request, f'Successfully reindexed {count} users')
            elif index_name == 'media':
                count = self.reindex_media()
                messages.success(request, f'Successfully reindexed {count} media files')
            else:
                messages.error(request, f'Unknown index: {index_name}')
                
        except Exception as e:
            messages.error(request, f'Reindexing failed: {e}')
        
        return redirect('admin:search_configuration')
    
    def clear_view(self, request, index_name):
        """Clear all documents from an index"""
        try:
            meili_client.clear_index(index_name)
            messages.success(request, f'Successfully cleared index: {index_name}')
        except Exception as e:
            messages.error(request, f'Failed to clear index: {e}')
        
        return redirect('admin:search_configuration')
    
    def get_search_status(self):
        """Get current search system status"""
        status = {
            'meilisearch_healthy': False,
            'indexes': []
        }
        
        try:
            # Check MeiliSearch health
            status['meilisearch_healthy'] = meili_client.health_check()
            
            # Get index information
            for index_name, config in settings.MEILISEARCH_INDEXES.items():
                index_info = {
                    'name': index_name,
                    'config': config,
                    'stats': None,
                    'exists': False
                }
                
                try:
                    stats = meili_client.get_index_stats(index_name)
                    if stats:
                        index_info['stats'] = stats
                        index_info['exists'] = True
                except:
                    pass
                
                status['indexes'].append(index_info)
                
        except Exception as e:
            status['error'] = str(e)
        
        return status
    
    def reindex_resources(self):
        """Reindex all resources"""
        from apps.content.serializers import ResourceSearchSerializer
        
        resources = Resource.objects.filter(is_active=True)
        documents = []
        
        for resource in resources:
            doc = ResourceSearchSerializer(resource).data
            documents.append(doc)
        
        if documents:
            meili_client.add_documents('resources', documents)
        
        return len(documents)
    
    def reindex_users(self):
        """Reindex all users"""
        users = User.objects.filter(is_active=True)
        documents = []
        
        for user in users:
            doc = {
                'id': str(user.id),
                'first_name': user.first_name,
                'last_name': user.last_name,
                'email': user.email,
                'organization': getattr(user, 'organization', ''),
                'role': user.role.name if user.role else '',
                'is_active': user.is_active,
                'email_verified': user.email_verified,
                'created_at': user.created_at.isoformat() if user.created_at else None,
                'last_login': user.last_login.isoformat() if user.last_login else None
            }
            documents.append(doc)
        
        if documents:
            meili_client.add_documents('users', documents)
        
        return len(documents)
    
    def reindex_media(self):
        """Reindex all media files"""
        media_files = MediaFile.objects.filter(is_active=True)
        documents = []
        
        for media_file in media_files:
            doc = {
                'id': str(media_file.id),
                'title': media_file.title,
                'description': media_file.description,
                'original_filename': media_file.original_filename,
                'tags': media_file.tags,
                'media_type': media_file.media_type,
                'uploaded_by': str(media_file.uploaded_by.id),
                'folder': str(media_file.folder.id) if media_file.folder else None,
                'created_at': media_file.created_at.isoformat() if media_file.created_at else None,
                'file_size': media_file.file_size
            }
            documents.append(doc)
        
        if documents:
            meili_client.add_documents('media', documents)
        
        return len(documents)


# Create a dummy model for the admin interface
class SearchConfiguration(models.Model):
    """Dummy model for search configuration admin"""
    class Meta:
        managed = False
        verbose_name = 'Search Configuration'
        verbose_name_plural = 'Search Configuration'


# Register the search configuration admin
admin.site.register(SearchConfiguration, SearchConfigurationAdmin)