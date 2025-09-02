"""
JWT token validation service for Auth0 integration
"""
import logging
from typing import Dict, Optional, Any, Union

import jwt
from django.conf import settings
from jwt import PyJWTError
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from .jwks import jwks_service, JWKSError

logger = logging.getLogger(__name__)


class JWTValidationError(Exception):
    """Base exception for JWT validation errors"""
    pass


class JWTExpiredError(JWTValidationError):
    """Exception raised when JWT token has expired"""
    pass


class JWTInvalidError(JWTValidationError):
    """Exception raised when JWT token is invalid"""
    pass


class JWTService:
    """
    Service for validating Auth0 JWT tokens
    """
    
    def __init__(self):
        self.algorithm = settings.AUTH0_ALGORITHM
        self.audience = settings.AUTH0_AUDIENCE
        self.issuer = settings.AUTH0_ISSUER
        self.leeway = settings.AUTH0_TOKEN_LEEWAY
        
    def _jwk_to_rsa_key(self, jwk: Dict[str, Any]) -> rsa.RSAPublicKey:
        """
        Convert JWK to RSA public key
        
        Args:
            jwk: JSON Web Key dictionary
            
        Returns:
            RSA public key object
            
        Raises:
            JWTInvalidError: If JWK conversion fails
        """
        try:
            # Convert base64url to integer
            def base64url_to_int(data: str) -> int:
                import base64
                # Add padding if needed
                missing_padding = len(data) % 4
                if missing_padding:
                    data += '=' * (4 - missing_padding)
                return int.from_bytes(base64.urlsafe_b64decode(data), 'big')
            
            n = base64url_to_int(jwk['n'])
            e = base64url_to_int(jwk['e'])
            
            # Create RSA public key
            public_numbers = rsa.RSAPublicNumbers(e, n)
            public_key = public_numbers.public_key()
            
            return public_key
            
        except Exception as exc:
            logger.error(f"Failed to convert JWK to RSA key: {exc}")
            raise JWTInvalidError(f"Failed to convert JWK to RSA key: {exc}")
    
    def _get_public_key(self, token_header: Dict[str, Any]) -> rsa.RSAPublicKey:
        """
        Get public key for token verification
        
        Args:
            token_header: JWT token header
            
        Returns:
            RSA public key for verification
            
        Raises:
            JWTInvalidError: If public key cannot be retrieved
        """
        try:
            kid = token_header.get('kid')
            if not kid:
                raise JWTInvalidError("Token header missing 'kid' field")
            
            # Get signing key from JWKS
            jwk = jwks_service.get_signing_key(kid)
            
            # Convert JWK to RSA public key
            public_key = self._jwk_to_rsa_key(jwk)
            
            return public_key
            
        except JWKSError as e:
            logger.error(f"JWKS error getting public key: {e}")
            raise JWTInvalidError(f"Failed to get public key: {e}")
        
        except Exception as e:
            logger.error(f"Unexpected error getting public key: {e}")
            raise JWTInvalidError(f"Failed to get public key: {e}")
    
    def decode_token(self, token: str, verify: bool = True) -> Dict[str, Any]:
        """
        Decode and validate JWT token
        
        Args:
            token: JWT token string
            verify: Whether to verify token signature and claims
            
        Returns:
            Decoded token payload
            
        Raises:
            JWTValidationError: If token validation fails
        """
        try:
            # Remove 'Bearer ' prefix if present
            if token.startswith('Bearer '):
                token = token[7:]
            
            if not verify:
                # Decode without verification (for debugging)
                return jwt.decode(token, options={"verify_signature": False})
            
            # Get token header to extract kid
            try:
                header = jwt.get_unverified_header(token)
            except PyJWTError as e:
                logger.error(f"Failed to get token header: {e}")
                raise JWTInvalidError(f"Invalid token header: {e}")
            
            # Get public key for verification
            public_key = self._get_public_key(header)
            
            # Decode and verify token
            payload = jwt.decode(
                token,
                public_key,
                algorithms=[self.algorithm],
                audience=self.audience,
                issuer=self.issuer,
                leeway=self.leeway,
                options={
                    'verify_signature': True,
                    'verify_exp': True,
                    'verify_nbf': True,
                    'verify_iat': True,
                    'verify_aud': True,
                    'verify_iss': True,
                }
            )
            
            logger.debug(f"Successfully validated token for user: {payload.get('sub')}")
            return payload
            
        except jwt.ExpiredSignatureError:
            logger.warning("Token has expired")
            raise JWTExpiredError("Token has expired")
        
        except jwt.InvalidAudienceError:
            logger.error(f"Invalid audience. Expected: {self.audience}")
            raise JWTInvalidError("Invalid token audience")
        
        except jwt.InvalidIssuerError:
            logger.error(f"Invalid issuer. Expected: {self.issuer}")
            raise JWTInvalidError("Invalid token issuer")
        
        except jwt.InvalidSignatureError:
            logger.error("Invalid token signature")
            raise JWTInvalidError("Invalid token signature")
        
        except jwt.InvalidTokenError as e:
            logger.error(f"Invalid token: {e}")
            raise JWTInvalidError(f"Invalid token: {e}")
        
        except JWTValidationError:
            # Re-raise our custom exceptions
            raise
        
        except Exception as e:
            logger.error(f"Unexpected error validating token: {e}")
            raise JWTInvalidError(f"Token validation failed: {e}")
    
    def extract_user_info(self, token_payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract user information from token payload
        
        Args:
            token_payload: Decoded JWT payload
            
        Returns:
            User information dictionary
        """
        user_info = {}
        
        # Extract standard claims
        user_info['auth0_id'] = token_payload.get('sub')
        user_info['email'] = token_payload.get('email')
        user_info['email_verified'] = token_payload.get('email_verified', False)
        user_info['name'] = token_payload.get('name')
        user_info['given_name'] = token_payload.get('given_name')
        user_info['family_name'] = token_payload.get('family_name')
        user_info['picture'] = token_payload.get('picture')
        user_info['locale'] = token_payload.get('locale')
        user_info['updated_at'] = token_payload.get('updated_at')
        
        # Extract custom role claim
        role_claim = settings.AUTH0_ROLE_CLAIM
        roles = token_payload.get(role_claim, [])
        if isinstance(roles, str):
            roles = [roles]
        user_info['roles'] = roles
        
        # Extract other custom claims
        for claim in settings.AUTH0_USER_INFO_CLAIMS:
            if claim not in user_info and claim in token_payload:
                user_info[claim] = token_payload[claim]
        
        # Remove None values
        user_info = {k: v for k, v in user_info.items() if v is not None}
        
        logger.debug(f"Extracted user info for: {user_info.get('email')}")
        return user_info
    
    def validate_token_and_extract_user(self, token: str) -> Dict[str, Any]:
        """
        Validate token and extract user information
        
        Args:
            token: JWT token string
            
        Returns:
            User information dictionary
            
        Raises:
            JWTValidationError: If token validation fails
        """
        payload = self.decode_token(token)
        return self.extract_user_info(payload)
    
    def get_token_info(self, token: str) -> Dict[str, Any]:
        """
        Get token information without full validation (for debugging)
        
        Args:
            token: JWT token string
            
        Returns:
            Token information dictionary
        """
        try:
            # Remove 'Bearer ' prefix if present
            if token.startswith('Bearer '):
                token = token[7:]
            
            header = jwt.get_unverified_header(token)
            payload = jwt.decode(token, options={"verify_signature": False})
            
            return {
                'header': header,
                'payload': payload,
                'algorithm': header.get('alg'),
                'key_id': header.get('kid'),
                'issued_at': payload.get('iat'),
                'expires_at': payload.get('exp'),
                'subject': payload.get('sub'),
                'audience': payload.get('aud'),
                'issuer': payload.get('iss'),
            }
            
        except Exception as e:
            logger.error(f"Failed to get token info: {e}")
            return {'error': str(e)}


# Global JWT service instance
jwt_service = JWTService()
