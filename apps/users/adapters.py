"""
Django Allauth adapters for custom user registration and social account handling
"""

from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib.auth import get_user_model

User = get_user_model()


class AccountAdapter(DefaultAccountAdapter):
    """
    Custom account adapter for handling user registration
    """
    
    def is_open_for_signup(self, request):
        """
        Allow user registration
        """
        return True
    
    def save_user(self, request, user, form, commit=True):
        """
        Save user with custom fields
        """

        # Set additional fields if needed
        if hasattr(form, 'cleaned_data'):
            user.name = form.cleaned_data.get('name', '')

        if commit:
            user.save()

        return user


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Custom social account adapter for handling OAuth2 registration
    """
    
    def is_open_for_signup(self, request, sociallogin):
        """
        Allow social account signup
        """
        return True
    
    def save_user(self, request, sociallogin, form=None):
        """
        Save user from social account data
        """
        user = sociallogin.user
        
        # Extract data from social account
        if sociallogin.account.provider == 'google':
            extra_data = sociallogin.account.extra_data
            user.name = extra_data.get('name', '')
            
        elif sociallogin.account.provider == 'github':
            extra_data = sociallogin.account.extra_data
            user.name = extra_data.get('name') or extra_data.get('login', '')
        
        user.save()
        return user
    
    def populate_user(self, request, sociallogin, data):
        """
        Populate user from social account data
        """
        user = super().populate_user(request, sociallogin, data)
        
        # Set additional fields based on provider
        if sociallogin.account.provider == 'google':
            extra_data = sociallogin.account.extra_data
            user.name = extra_data.get('name', '')
            
        elif sociallogin.account.provider == 'github':
            extra_data = sociallogin.account.extra_data
            user.name = extra_data.get('name') or extra_data.get('login', '')
        
        return user
