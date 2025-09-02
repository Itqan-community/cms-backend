"""
API Key Authentication for Django REST Framework
"""
import time
from django.contrib.auth.models import AnonymousUser
from django.utils import timezone
from rest_framework import authentication, exceptions
from rest_framework.throttling import BaseThrottle
from .models import APIKey, APIKeyUsage, RateLimitEvent


class APIKeyAuthentication(authentication.BaseAuthentication):
    """
    Custom authentication class for API key authentication
    """
    keyword = 'Bearer'
    
    def authenticate(self, request):
        """
        Authenticate the request and return a two-tuple of (user, token)
        """
        auth_header = self.get_authorization_header(request)
        if not auth_header:
            return None
        
        try:
            auth_parts = auth_header.split()
        except UnicodeDecodeError:
            msg = 'Invalid token header. Token string should not contain invalid characters.'
            raise exceptions.AuthenticationFailed(msg)
        
        if not auth_parts or auth_parts[0].lower() != self.keyword.lower().encode():
            return None
        
        if len(auth_parts) == 1:
            msg = 'Invalid token header. No credentials provided.'
            raise exceptions.AuthenticationFailed(msg)
        elif len(auth_parts) > 2:
            msg = 'Invalid token header. Token string should not contain spaces.'
            raise exceptions.AuthenticationFailed(msg)
        
        try:
            token = auth_parts[1].decode()
        except UnicodeDecodeError:
            msg = 'Invalid token header. Token string should not contain invalid characters.'
            raise exceptions.AuthenticationFailed(msg)
        
        return self.authenticate_credentials(token, request)
    
    def authenticate_credentials(self, key, request):
        """
        Authenticate the API key and return user
        """
        user, api_key = APIKey.authenticate(key)
        
        if not user:
            raise exceptions.AuthenticationFailed('Invalid API key.')
        
        if not api_key.is_valid():
            raise exceptions.AuthenticationFailed('API key is expired or revoked.')
        
        # Check IP restrictions
        if api_key.allowed_ips:
            client_ip = self.get_client_ip(request)
            if not self.is_ip_allowed(client_ip, api_key.allowed_ips):
                raise exceptions.AuthenticationFailed('IP address not allowed for this API key.')
        
        # Store API key in request for later use
        request.api_key = api_key
        
        return (user, api_key)
    
    def get_authorization_header(self, request):
        """
        Return request's 'Authorization:' header, as a bytestring.
        """
        auth = request.META.get('HTTP_AUTHORIZATION', b'')
        if isinstance(auth, str):
            auth = auth.encode('iso-8859-1')
        return auth
    
    def get_client_ip(self, request):
        """
        Get the client IP address from the request
        """
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def is_ip_allowed(self, client_ip, allowed_ips):
        """
        Check if client IP is in the allowed IP list
        """
        import ipaddress
        
        try:
            client_ip_obj = ipaddress.ip_address(client_ip)
        except ValueError:
            return False
        
        for allowed_ip in allowed_ips:
            try:
                if '/' in allowed_ip:
                    # CIDR notation
                    network = ipaddress.ip_network(allowed_ip, strict=False)
                    if client_ip_obj in network:
                        return True
                else:
                    # Single IP
                    if str(client_ip_obj) == allowed_ip:
                        return True
            except ValueError:
                continue
        
        return False


class APIKeyThrottle(BaseThrottle):
    """
    Throttle for API key based rate limiting
    """
    cache_format = 'throttle_%(scope)s_%(ident)s'
    timer = time.time
    
    def __init__(self):
        self.num_requests = None
        self.duration = None
    
    def allow_request(self, request, view):
        """
        Implement the check to see if the request should be throttled.
        """
        if not hasattr(request, 'api_key') or not request.api_key:
            # No API key, use default throttling
            return True
        
        api_key = request.api_key
        
        # Get rate limit for this API key
        self.num_requests = api_key.rate_limit
        self.duration = 3600  # 1 hour in seconds
        
        if self.num_requests is None:
            return True
        
        self.key = self.get_cache_key(request, view)
        if self.key is None:
            return True
        
        self.history = self.cache.get(self.key, [])
        self.now = self.timer()
        
        # Drop any requests from the history which have now passed the throttle duration
        while self.history and self.history[-1] <= self.now - self.duration:
            self.history.pop()
        
        if len(self.history) >= self.num_requests:
            # Log rate limit event
            self.log_rate_limit_event(request, api_key)
            return self.throttle_failure()
        
        return self.throttle_success()
    
    def get_cache_key(self, request, view):
        """
        Create a cache key for the API key
        """
        if hasattr(request, 'api_key') and request.api_key:
            ident = str(request.api_key.id)
        else:
            # Fallback to IP-based throttling
            ident = self.get_ident(request)
        
        return self.cache_format % {
            'scope': 'api_key',
            'ident': ident,
        }
    
    def throttle_success(self):
        """
        Inserts the current request's timestamp along with the key
        into the cache.
        """
        self.history.insert(0, self.now)
        self.cache.set(self.key, self.history, self.duration)
        return True
    
    def throttle_failure(self):
        """
        Called when a request to the API has failed due to throttling.
        """
        return False
    
    def wait(self):
        """
        Returns the recommended next request time in seconds.
        """
        if self.history:
            remaining_duration = self.duration - (self.now - self.history[-1])
        else:
            remaining_duration = self.duration
        
        available_requests = self.num_requests - len(self.history) + 1
        if available_requests <= 0:
            return None
        
        return remaining_duration / float(available_requests)
    
    def log_rate_limit_event(self, request, api_key):
        """
        Log rate limit violation
        """
        try:
            # Get client IP
            client_ip = self.get_client_ip(request)
            
            # Create rate limit event
            RateLimitEvent.objects.create(
                api_key=api_key,
                ip_address=client_ip,
                endpoint=request.path,
                method=request.method,
                limit_type='api_key',
                current_count=len(self.history),
                limit_value=self.num_requests,
                window_seconds=self.duration
            )
        except Exception as e:
            # Don't let logging errors break the request
            import logging
            logger = logging.getLogger('itqan.api_keys')
            logger.error(f"Failed to log rate limit event: {e}")
    
    def get_client_ip(self, request):
        """
        Get the client IP address from the request
        """
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class APIUsageMiddleware:
    """
    Middleware to log API usage for analytics
    """
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Record start time
        start_time = time.time()
        
        response = self.get_response(request)
        
        # Log API usage if this was an API request with an API key
        if (hasattr(request, 'api_key') and 
            request.api_key and 
            request.path.startswith('/api/')):
            
            try:
                self.log_api_usage(request, response, start_time)
            except Exception as e:
                # Don't let logging errors break the request
                import logging
                logger = logging.getLogger('itqan.api_keys')
                logger.error(f"Failed to log API usage: {e}")
        
        return response
    
    def log_api_usage(self, request, response, start_time):
        """
        Log API usage to the database
        """
        end_time = time.time()
        response_time = (end_time - start_time) * 1000  # Convert to milliseconds
        
        # Get client IP
        client_ip = self.get_client_ip(request)
        
        # Get user agent
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        # Prepare request data (be careful not to log sensitive information)
        request_data = {
            'query_params': dict(request.GET),
            'content_type': request.content_type,
        }
        
        # Create usage log
        APIKeyUsage.objects.create(
            api_key=request.api_key,
            endpoint=request.path,
            method=request.method,
            status_code=response.status_code,
            ip_address=client_ip,
            user_agent=user_agent,
            request_data=request_data,
            response_time=response_time
        )
        
        # Update API key last used info
        request.api_key.update_last_used(client_ip)
    
    def get_client_ip(self, request):
        """
        Get the client IP address from the request
        """
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
