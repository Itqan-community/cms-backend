"""
Mock API Authentication System
Handles authentication only for mock API endpoints using mock tokens
"""
import json
import base64
from rest_framework import authentication, exceptions
from rest_framework.permissions import AllowAny


class MockTokenAuthentication(authentication.BaseAuthentication):
    """
    Authentication class that validates mock JWT tokens for mock API endpoints only
    """
    keyword = 'Bearer'
    
    def authenticate(self, request):
        """
        Authenticate mock JWT tokens only
        """
        auth_header = self.get_authorization_header(request)
        if not auth_header:
            return None
        
        try:
            auth_parts = auth_header.split()
        except UnicodeDecodeError:
            return None
        
        if not auth_parts or auth_parts[0].lower() != self.keyword.lower().encode():
            return None
        
        if len(auth_parts) == 1:
            return None
        elif len(auth_parts) > 2:
            return None
        
        try:
            token = auth_parts[1].decode()
        except UnicodeDecodeError:
            return None
        
        return self.authenticate_mock_token(token)
    
    def authenticate_mock_token(self, token):
        """
        Validate mock JWT token format and extract user info
        """
        try:
            # Split the token into parts (header.payload.signature)
            parts = token.split('.')
            if len(parts) != 3:
                return None
            
            header_b64, payload_b64, signature = parts
            
            # Check if this is a mock token by looking at the signature
            if not signature.startswith('mock_signature_'):
                return None
            
            # Decode the payload to get user info
            # Add padding if needed for base64 decoding
            payload_b64 += '=' * (4 - len(payload_b64) % 4)
            payload_bytes = base64.b64decode(payload_b64)
            payload = json.loads(payload_bytes)
            
            # Validate token structure
            if 'user_id' not in payload or 'type' not in payload:
                return None
            
            # Create a mock user object
            mock_user = MockUser(payload['user_id'])
            
            return (mock_user, token)
            
        except (ValueError, json.JSONDecodeError, base64.binascii.Error):
            return None
    
    def get_authorization_header(self, request):
        """
        Return request's 'Authorization:' header, as a bytestring.
        """
        auth = request.META.get('HTTP_AUTHORIZATION', b'')
        if isinstance(auth, str):
            auth = auth.encode('iso-8859-1')
        return auth


class MockUser:
    """
    Mock user object for mock authentication
    """
    def __init__(self, user_id):
        self.id = user_id
        self.is_authenticated = True
        self.is_active = True
        self.is_anonymous = False
    
    def __str__(self):
        return f"MockUser({self.id})"


class MockTokenPermission(AllowAny):
    """
    Permission class that allows mock token access to mock endpoints
    """
    def has_permission(self, request, view):
        # Always allow access for mock API endpoints
        return True
