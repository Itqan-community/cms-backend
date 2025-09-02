"""
MeiliSearch client for Itqan CMS
"""
import logging
from typing import Dict, List, Optional, Any
from django.conf import settings
import meilisearch
from meilisearch.models.task import TaskInfo

logger = logging.getLogger(__name__)


class MeiliSearchClient:
    """
    Wrapper for MeiliSearch client with error handling and configuration
    """
    
    def __init__(self):
        self.client = meilisearch.Client(
            url=settings.MEILISEARCH_URL,
            api_key=settings.MEILISEARCH_MASTER_KEY,
            timeout=settings.MEILISEARCH_TIMEOUT
        )
        self._indexes = {}
    
    def get_index(self, index_name: str):
        """Get or create a MeiliSearch index"""
        if index_name not in self._indexes:
            try:
                # Try to get existing index
                self._indexes[index_name] = self.client.index(index_name)
                
                # Verify index exists
                self._indexes[index_name].get_stats()
                
            except meilisearch.errors.MeilisearchApiError as e:
                if e.code == 'index_not_found':
                    logger.info(f"Creating new MeiliSearch index: {index_name}")
                    self.create_index(index_name)
                else:
                    logger.error(f"MeiliSearch error for index {index_name}: {e}")
                    raise
        
        return self._indexes[index_name]
    
    def create_index(self, index_name: str) -> bool:
        """Create a new MeiliSearch index with configuration"""
        try:
            config = settings.MEILISEARCH_INDEXES.get(index_name, {})
            
            # Create index
            task_info = self.client.create_index(
                uid=index_name,
                options={'primaryKey': config.get('primary_key', 'id')}
            )
            
            # Wait for index creation
            self.client.wait_for_task(task_info.task_uid)
            
            # Get the created index
            index = self.client.index(index_name)
            self._indexes[index_name] = index
            
            # Configure index settings
            self._configure_index(index, config)
            
            logger.info(f"Successfully created MeiliSearch index: {index_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create MeiliSearch index {index_name}: {e}")
            return False
    
    def _configure_index(self, index, config: Dict):
        """Configure index settings"""
        try:
            # Set searchable attributes
            if 'searchable_attributes' in config:
                task = index.update_searchable_attributes(config['searchable_attributes'])
                self.client.wait_for_task(task.task_uid)
            
            # Set filterable attributes
            if 'filterable_attributes' in config:
                task = index.update_filterable_attributes(config['filterable_attributes'])
                self.client.wait_for_task(task.task_uid)
            
            # Set sortable attributes
            if 'sortable_attributes' in config:
                task = index.update_sortable_attributes(config['sortable_attributes'])
                self.client.wait_for_task(task.task_uid)
            
            # Set ranking rules
            if 'ranking_rules' in config:
                task = index.update_ranking_rules(config['ranking_rules'])
                self.client.wait_for_task(task.task_uid)
            
            logger.info(f"Configured index settings for: {index.uid}")
            
        except Exception as e:
            logger.error(f"Failed to configure index {index.uid}: {e}")
    
    def add_documents(self, index_name: str, documents: List[Dict]) -> Optional[TaskInfo]:
        """Add documents to an index"""
        try:
            index = self.get_index(index_name)
            task_info = index.add_documents(documents)
            logger.info(f"Added {len(documents)} documents to {index_name}")
            return task_info
            
        except Exception as e:
            logger.error(f"Failed to add documents to {index_name}: {e}")
            return None
    
    def update_documents(self, index_name: str, documents: List[Dict]) -> Optional[TaskInfo]:
        """Update documents in an index"""
        try:
            index = self.get_index(index_name)
            task_info = index.update_documents(documents)
            logger.info(f"Updated {len(documents)} documents in {index_name}")
            return task_info
            
        except Exception as e:
            logger.error(f"Failed to update documents in {index_name}: {e}")
            return None
    
    def delete_document(self, index_name: str, document_id: str) -> Optional[TaskInfo]:
        """Delete a document from an index"""
        try:
            index = self.get_index(index_name)
            task_info = index.delete_document(document_id)
            logger.info(f"Deleted document {document_id} from {index_name}")
            return task_info
            
        except Exception as e:
            logger.error(f"Failed to delete document {document_id} from {index_name}: {e}")
            return None
    
    def search(self, index_name: str, query: str, **kwargs) -> Optional[Dict]:
        """Search documents in an index"""
        try:
            index = self.get_index(index_name)
            results = index.search(query, kwargs)
            return results
            
        except Exception as e:
            logger.error(f"Search failed in {index_name}: {e}")
            return None
    
    def clear_index(self, index_name: str) -> Optional[TaskInfo]:
        """Clear all documents from an index"""
        try:
            index = self.get_index(index_name)
            task_info = index.delete_all_documents()
            logger.info(f"Cleared all documents from {index_name}")
            return task_info
            
        except Exception as e:
            logger.error(f"Failed to clear index {index_name}: {e}")
            return None
    
    def get_index_stats(self, index_name: str) -> Optional[Dict]:
        """Get statistics for an index"""
        try:
            index = self.get_index(index_name)
            return index.get_stats()
            
        except Exception as e:
            logger.error(f"Failed to get stats for {index_name}: {e}")
            return None
    
    def wait_for_task(self, task_uid: int, timeout: int = 30) -> bool:
        """Wait for a task to complete"""
        try:
            self.client.wait_for_task(task_uid, timeout_in_ms=timeout * 1000)
            return True
        except Exception as e:
            logger.error(f"Task {task_uid} failed or timed out: {e}")
            return False
    
    def health_check(self) -> bool:
        """Check if MeiliSearch is healthy"""
        try:
            health = self.client.health()
            return health.get('status') == 'available'
        except Exception as e:
            logger.error(f"MeiliSearch health check failed: {e}")
            return False


# Global client instance
meili_client = MeiliSearchClient()
