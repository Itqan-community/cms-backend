"""
Management command for setting up and managing search indexes
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from apps.search.client import meili_client
from apps.search.tasks import bulk_index_resources


class Command(BaseCommand):
    help = 'Setup and manage MeiliSearch indexes for Itqan CMS'

    def add_arguments(self, parser):
        parser.add_argument(
            '--create-indexes',
            action='store_true',
            help='Create MeiliSearch indexes with proper configuration',
        )
        parser.add_argument(
            '--rebuild-indexes',
            action='store_true',
            help='Rebuild all search indexes from scratch',
        )
        parser.add_argument(
            '--health-check',
            action='store_true',
            help='Check MeiliSearch connectivity and health',
        )
        parser.add_argument(
            '--stats',
            action='store_true',
            help='Show search index statistics',
        )
        parser.add_argument(
            '--clear-indexes',
            action='store_true',
            help='Clear all documents from search indexes',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('🔍 MeiliSearch Management for Itqan CMS')
        )

        if options['health_check']:
            self.health_check()
        
        if options['create_indexes']:
            self.create_indexes()
        
        if options['clear_indexes']:
            self.clear_indexes()
        
        if options['rebuild_indexes']:
            self.rebuild_indexes()
        
        if options['stats']:
            self.show_stats()

        if not any(options.values()):
            self.stdout.write(
                self.style.WARNING('No action specified. Use --help to see available options.')
            )

    def health_check(self):
        """Check MeiliSearch health"""
        self.stdout.write('Checking MeiliSearch health...')
        
        try:
            is_healthy = meili_client.health_check()
            
            if is_healthy:
                self.stdout.write(
                    self.style.SUCCESS('✅ MeiliSearch is healthy and accessible')
                )
            else:
                self.stdout.write(
                    self.style.ERROR('❌ MeiliSearch is not healthy')
                )
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ MeiliSearch health check failed: {e}')
            )

    def create_indexes(self):
        """Create and configure search indexes"""
        self.stdout.write('Creating MeiliSearch indexes...')
        
        try:
            # Create resources index
            success = meili_client.create_index('resources')
            
            if success:
                self.stdout.write(
                    self.style.SUCCESS('✅ Resources index created and configured')
                )
            else:
                self.stdout.write(
                    self.style.ERROR('❌ Failed to create resources index')
                )
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Index creation failed: {e}')
            )

    def clear_indexes(self):
        """Clear all documents from indexes"""
        self.stdout.write('Clearing search indexes...')
        
        try:
            task_info = meili_client.clear_index('resources')
            
            if task_info:
                # Wait for completion
                success = meili_client.wait_for_task(task_info.task_uid)
                
                if success:
                    self.stdout.write(
                        self.style.SUCCESS('✅ Search indexes cleared')
                    )
                else:
                    self.stdout.write(
                        self.style.ERROR('❌ Failed to clear indexes (task failed)')
                    )
            else:
                self.stdout.write(
                    self.style.ERROR('❌ Failed to initiate index clearing')
                )
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Index clearing failed: {e}')
            )

    def rebuild_indexes(self):
        """Rebuild all search indexes"""
        self.stdout.write('Rebuilding search indexes...')
        
        try:
            # Clear existing indexes
            self.stdout.write('Clearing existing indexes...')
            self.clear_indexes()
            
            # Reindex all resources
            self.stdout.write('Starting bulk reindexing...')
            
            # Use synchronous approach for management command
            from apps.content.models import Resource
            from apps.search.serializers import ResourceSearchSerializer
            
            # Get all published, active resources
            resources = Resource.objects.select_related('publisher', 'publisher__role').filter(
                is_active=True,
                published_at__isnull=False
            )
            
            total_count = resources.count()
            self.stdout.write(f'Found {total_count} resources to index')
            
            if total_count == 0:
                self.stdout.write(
                    self.style.WARNING('No resources found to index')
                )
                return
            
            # Process in batches
            batch_size = 100
            indexed_count = 0
            
            for offset in range(0, total_count, batch_size):
                batch = resources[offset:offset + batch_size]
                documents = []
                
                for resource in batch:
                    try:
                        serializer = ResourceSearchSerializer(resource)
                        documents.append(serializer.data)
                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(f'Failed to serialize resource {resource.id}: {e}')
                        )
                
                if documents:
                    # Index batch
                    task_info = meili_client.update_documents('resources', documents)
                    if task_info:
                        success = meili_client.wait_for_task(task_info.task_uid)
                        if success:
                            indexed_count += len(documents)
                            self.stdout.write(f'Indexed batch: {indexed_count}/{total_count}')
                        else:
                            self.stdout.write(
                                self.style.ERROR(f'Failed to index batch of {len(documents)} resources')
                            )
            
            self.stdout.write(
                self.style.SUCCESS(f'✅ Rebuild completed: {indexed_count}/{total_count} resources indexed')
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Index rebuild failed: {e}')
            )

    def show_stats(self):
        """Show search index statistics"""
        self.stdout.write('Getting search index statistics...')
        
        try:
            stats = meili_client.get_index_stats('resources')
            
            if stats:
                self.stdout.write(
                    self.style.SUCCESS(f'''
📊 Resources Index Statistics:
   • Documents: {stats.get('numberOfDocuments', 'N/A')}
   • Is indexing: {stats.get('isIndexing', 'N/A')}
   • Field distribution: {stats.get('fieldDistribution', 'N/A')}
                    ''')
                )
            else:
                self.stdout.write(
                    self.style.ERROR('❌ Failed to retrieve index statistics')
                )
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Failed to get statistics: {e}')
            )
