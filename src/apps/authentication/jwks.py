"""
JWKS (JSON Web Key Set) service for Auth0 integration
"""
import json
import logging
import time
from typing import Dict, Optional, Any
from urllib.parse import urljoin

import requests
from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger(__name__)


class JWKSError(Exception):
    """Base exception for JWKS-related errors"""
    pass


class JWKSFetchError(JWKSError):
    """Exception raised when fetching JWKS fails"""
    pass


class JWKSKeyNotFoundError(JWKSError):
    """Exception raised when a specific key is not found in JWKS"""
    pass


class JWKSService:
    """
    Service for fetching and caching Auth0 JWKS (JSON Web Key Set)
    """
    
    def __init__(self):
        self.jwks_url = settings.AUTH0_JWKS_URL
        self.cache_ttl = settings.AUTH0_JWKS_CACHE_TTL
        self.cache_key = 'auth0_jwks'
        self.timeout = 10  # HTTP request timeout
    
    def get_jwks(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Get JWKS from cache or fetch from Auth0
        
        Args:
            force_refresh: Force refresh from Auth0 (bypass cache)
            
        Returns:
            JWKS dictionary
            
        Raises:
            JWKSFetchError: If fetching JWKS fails
        """
        if not force_refresh:
            # Try to get from cache first
            cached_jwks = cache.get(self.cache_key)
            if cached_jwks:
                logger.debug("Using cached JWKS")
                return cached_jwks
        
        # Fetch from Auth0
        try:
            logger.info(f"Fetching JWKS from {self.jwks_url}")
            
            response = requests.get(
                self.jwks_url,
                timeout=self.timeout,
                headers={
                    'User-Agent': 'Itqan-CMS/1.0',
                    'Accept': 'application/json',
                }
            )
            response.raise_for_status()
            
            jwks = response.json()
            
            # Validate JWKS structure
            if not isinstance(jwks, dict) or 'keys' not in jwks:
                raise JWKSFetchError("Invalid JWKS structure: missing 'keys' field")
            
            if not isinstance(jwks['keys'], list):
                raise JWKSFetchError("Invalid JWKS structure: 'keys' is not a list")
            
            # Cache the JWKS
            cache.set(self.cache_key, jwks, self.cache_ttl)
            logger.info(f"Cached JWKS with {len(jwks['keys'])} keys for {self.cache_ttl} seconds")
            
            return jwks
            
        except requests.exceptions.Timeout:
            logger.error(f"Timeout fetching JWKS from {self.jwks_url}")
            raise JWKSFetchError("Timeout fetching JWKS")
        
        except requests.exceptions.ConnectionError:
            logger.error(f"Connection error fetching JWKS from {self.jwks_url}")
            raise JWKSFetchError("Connection error fetching JWKS")
        
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error fetching JWKS: {e}")
            raise JWKSFetchError(f"HTTP error fetching JWKS: {e}")
        
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in JWKS response: {e}")
            raise JWKSFetchError("Invalid JSON in JWKS response")
        
        except Exception as e:
            logger.error(f"Unexpected error fetching JWKS: {e}")
            raise JWKSFetchError(f"Unexpected error fetching JWKS: {e}")
    
    def get_key_by_kid(self, kid: str, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Get a specific key by its key ID (kid)
        
        Args:
            kid: Key ID to look for
            force_refresh: Force refresh JWKS from Auth0
            
        Returns:
            JWK (JSON Web Key) dictionary
            
        Raises:
            JWKSKeyNotFoundError: If key is not found
            JWKSFetchError: If fetching JWKS fails
        """
        jwks = self.get_jwks(force_refresh=force_refresh)
        
        for key in jwks['keys']:
            if key.get('kid') == kid:
                logger.debug(f"Found key with kid: {kid}")
                return key
        
        # Key not found, try refreshing once if not already done
        if not force_refresh:
            logger.info(f"Key {kid} not found in cache, refreshing JWKS")
            return self.get_key_by_kid(kid, force_refresh=True)
        
        # Still not found after refresh
        logger.error(f"Key with kid '{kid}' not found in JWKS")
        raise JWKSKeyNotFoundError(f"Key with kid '{kid}' not found")
    
    def get_signing_key(self, kid: str) -> Dict[str, Any]:
        """
        Get a signing key suitable for JWT verification
        
        Args:
            kid: Key ID to look for
            
        Returns:
            Signing key dictionary with required fields
            
        Raises:
            JWKSKeyNotFoundError: If key is not found or invalid
            JWKSFetchError: If fetching JWKS fails
        """
        key = self.get_key_by_kid(kid)
        
        # Validate key has required fields for RS256
        required_fields = ['kty', 'use', 'n', 'e']
        missing_fields = [field for field in required_fields if field not in key]
        
        if missing_fields:
            logger.error(f"Key {kid} missing required fields: {missing_fields}")
            raise JWKSKeyNotFoundError(f"Key {kid} missing required fields: {missing_fields}")
        
        # Validate key type and usage
        if key.get('kty') != 'RSA':
            logger.error(f"Key {kid} has unsupported key type: {key.get('kty')}")
            raise JWKSKeyNotFoundError(f"Key {kid} has unsupported key type")
        
        if key.get('use') != 'sig':
            logger.error(f"Key {kid} is not for signing: {key.get('use')}")
            raise JWKSKeyNotFoundError(f"Key {kid} is not for signing")
        
        # Check if algorithm is supported
        alg = key.get('alg', 'RS256')
        if alg not in ['RS256', 'RS384', 'RS512']:
            logger.error(f"Key {kid} has unsupported algorithm: {alg}")
            raise JWKSKeyNotFoundError(f"Key {kid} has unsupported algorithm")
        
        logger.debug(f"Retrieved valid signing key {kid} (algorithm: {alg})")
        return key
    
    def clear_cache(self) -> bool:
        """
        Clear JWKS cache
        
        Returns:
            True if cache was cleared
        """
        try:
            cache.delete(self.cache_key)
            logger.info("JWKS cache cleared")
            return True
        except Exception as e:
            logger.error(f"Failed to clear JWKS cache: {e}")
            return False
    
    def get_cache_info(self) -> Dict[str, Any]:
        """
        Get information about JWKS cache
        
        Returns:
            Cache information dictionary
        """
        cached_jwks = cache.get(self.cache_key)
        
        if cached_jwks:
            num_keys = len(cached_jwks.get('keys', []))
            return {
                'cached': True,
                'num_keys': num_keys,
                'cache_key': self.cache_key,
                'cache_ttl': self.cache_ttl,
            }
        else:
            return {
                'cached': False,
                'cache_key': self.cache_key,
                'cache_ttl': self.cache_ttl,
            }
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on JWKS service
        
        Returns:
            Health check results
        """
        start_time = time.time()
        
        try:
            jwks = self.get_jwks()
            end_time = time.time()
            
            return {
                'healthy': True,
                'num_keys': len(jwks.get('keys', [])),
                'response_time_ms': round((end_time - start_time) * 1000, 2),
                'jwks_url': self.jwks_url,
                'cache_info': self.get_cache_info(),
            }
            
        except Exception as e:
            end_time = time.time()
            
            return {
                'healthy': False,
                'error': str(e),
                'error_type': type(e).__name__,
                'response_time_ms': round((end_time - start_time) * 1000, 2),
                'jwks_url': self.jwks_url,
                'cache_info': self.get_cache_info(),
            }


# Global JWKS service instance
jwks_service = JWKSService()
