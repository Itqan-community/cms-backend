"""
Custom allauth adapters for user registration and authentication
"""
from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.socialaccount.models import SocialAccount
from django.contrib.auth import get_user_model
from django.conf import settings

User = get_user_model()


class AccountAdapter(DefaultAccountAdapter):
    """
    Custom account adapter for email/password registration
    """
    
    def save_user(self, request, user, form, commit=True):
        """
        Save user with additional profile data
        """
        # Call parent save_user first
        user = super().save_user(request, user, form, commit=False)
        
        # Set additional fields
        user.auth_provider = 'email'
        user.email_verified = False  # Will be set to True after email verification
        
        # Extract name if provided
        if hasattr(form, 'cleaned_data'):
            name = form.cleaned_data.get('name', '')
            if name:
                name_parts = name.strip().split(' ', 1)
                user.first_name = name_parts[0]
                if len(name_parts) > 1:
                    user.last_name = name_parts[1]
        
        if commit:
            user.save()
        
        return user
    
    def confirm_email(self, request, email_address):
        """
        Mark email as verified when confirmed
        """
        super().confirm_email(request, email_address)
        
        # Update user's email_verified status
        user = email_address.user
        user.email_verified = True
        user.save(update_fields=['email_verified'])


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Custom social account adapter for OAuth providers
    """
    
    def save_user(self, request, sociallogin, form=None):
        """
        Save user from social login
        """
        user = super().save_user(request, sociallogin, form)
        
        # Update user with social account data
        self.populate_user_from_social_account(user, sociallogin)
        
        return user
    
    def populate_user_from_social_account(self, user, sociallogin):
        """
        Populate user fields from social account data
        """
        account = sociallogin.account
        provider = account.provider
        extra_data = account.extra_data
        
        # Set auth provider
        user.auth_provider = provider
        user.email_verified = True  # Social accounts are considered verified
        
        # Update fields based on provider
        if provider == 'google':
            user.avatar_url = extra_data.get('picture', '')
            if not user.first_name:
                user.first_name = extra_data.get('given_name', '')
            if not user.last_name:
                user.last_name = extra_data.get('family_name', '')
                
        elif provider == 'github':
            user.avatar_url = extra_data.get('avatar_url', '')
            user.github_username = extra_data.get('login', '')
            user.bio = extra_data.get('bio', '') or user.bio
            user.location = extra_data.get('location', '') or user.location
            user.website = extra_data.get('blog', '') or user.website
            
            # For GitHub, name might be in 'name' field
            name = extra_data.get('name', '')
            if name and not (user.first_name and user.last_name):
                name_parts = name.strip().split(' ', 1)
                if not user.first_name:
                    user.first_name = name_parts[0]
                if len(name_parts) > 1 and not user.last_name:
                    user.last_name = name_parts[1]
        
        # Update profile completion status
        user.update_profile_completion_status()
        user.save()
    
    def pre_social_login(self, request, sociallogin):
        """
        Connect social account to existing user if email matches
        """
        # If user is already logged in, connect the account
        if request.user.is_authenticated:
            return
        
        # Try to connect to existing user by email
        try:
            email = sociallogin.user.email
            if email:
                existing_user = User.objects.get(email=email)
                sociallogin.connect(request, existing_user)
        except User.DoesNotExist:
            pass
