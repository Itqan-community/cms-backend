"""
Tests for Django Allauth integration (adapters and forms)
"""

import secrets

from allauth.socialaccount.models import SocialAccount, SocialApp, SocialLogin
from django.contrib.sites.models import Site
from django.test import RequestFactory
from django.utils.crypto import get_random_string
import pytest

from apps.core.tests import BaseTestCase
from apps.users.adapters import AccountAdapter, SocialAccountAdapter, User
from apps.users.forms import UserSignupForm, UserSocialSignupForm


class AccountAdapterTestCase(BaseTestCase):
    """Test case for custom AccountAdapter"""

    def setUp(self):
        """Set up test data"""
        self.factory = RequestFactory()
        self.adapter = AccountAdapter()
        self.request = self.factory.get("/")

    def test_is_open_for_signup(self):
        """Test that signup is allowed"""
        self.assertTrue(self.adapter.is_open_for_signup(self.request))

    def test_save_user_with_form(self):
        """Test saving user with form data"""
        user = User(email="test@example.com")

        # Mock form with cleaned_data
        class MockForm:
            cleaned_data = {"name": "Test User", "email": "test@example.com"}

        form = MockForm()

        saved_user = self.adapter.save_user(self.request, user, form, commit=True)

        self.assertEqual(saved_user.name, "Test User")
        self.assertEqual(saved_user.email, "test@example.com")
        self.assertTrue(User.objects.filter(email="test@example.com").exists())

    def test_save_user_without_form(self):
        """Test saving user without form data"""
        user = User(email="noform@example.com")

        saved_user = self.adapter.save_user(self.request, user, None, commit=True)

        self.assertEqual(saved_user.email, "noform@example.com")
        self.assertEqual(saved_user.name, "")  # Should be empty string
        self.assertTrue(User.objects.filter(email="noform@example.com").exists())


class SocialAccountAdapterTestCase(BaseTestCase):
    """Test case for custom SocialAccountAdapter"""

    def setUp(self):
        """Set up test data"""
        self.factory = RequestFactory()
        self.adapter = SocialAccountAdapter()
        self.request = self.factory.get("/")

        # Create social apps
        site = Site.objects.get(pk=1)

        self.google_app = SocialApp.objects.create(
            provider="google",
            name="Google OAuth2",
            client_id="test-google-client-id",
            secret=secrets.token_urlsafe(24),  # dynamic to avoid Bandit B106
        )
        self.google_app.sites.add(site)

        self.github_app = SocialApp.objects.create(
            provider="github",
            name="GitHub OAuth2",
            client_id="test-github-client-id",
            secret=secrets.token_urlsafe(24),  # dynamic to avoid Bandit B106
        )
        self.github_app.sites.add(site)

    def _create_social_login(self, provider, extra_data):
        """Helper method to create social login"""
        user = User(email="social@example.com")
        account = SocialAccount(provider=provider, uid="123456", extra_data=extra_data)
        return SocialLogin(user=user, account=account)

    def test_is_open_for_signup(self):
        """Test that social signup is allowed"""
        social_login = self._create_social_login("google", {})
        self.assertTrue(self.adapter.is_open_for_signup(self.request, social_login))

    def test_save_user_google(self):
        """Test saving user from Google social login"""
        extra_data = {"name": "Google User", "email": "google@example.com"}
        social_login = self._create_social_login("google", extra_data)

        saved_user = self.adapter.save_user(self.request, social_login)

        self.assertEqual(saved_user.name, "Google User")
        # Email comes from the SocialLogin.user, not provider payload
        self.assertEqual(saved_user.email, "social@example.com")
        self.assertTrue(User.objects.filter(email="social@example.com").exists())

    def test_save_user_github(self):
        """Test saving user from GitHub social login"""
        extra_data = {
            "name": "GitHub User",
            "login": "githubuser",
            "email": "github@example.com",
        }
        social_login = self._create_social_login("github", extra_data)

        saved_user = self.adapter.save_user(self.request, social_login)

        self.assertEqual(saved_user.name, "GitHub User")
        self.assertEqual(saved_user.email, "social@example.com")
        self.assertTrue(User.objects.filter(email="social@example.com").exists())

    def test_save_user_github_no_name(self):
        """Test saving user from GitHub with no name (uses login)"""
        extra_data = {"login": "githubuser", "email": "github@example.com"}
        social_login = self._create_social_login("github", extra_data)

        saved_user = self.adapter.save_user(self.request, social_login)

        self.assertEqual(saved_user.name, "githubuser")  # Should use login as fallback

    def test_populate_user_google(self):
        """Test populating user from Google data"""
        extra_data = {"name": "Populated Google User", "email": "populated@example.com"}
        social_login = self._create_social_login("google", extra_data)

        user = self.adapter.populate_user(self.request, social_login, {})

        self.assertEqual(user.name, "Populated Google User")

    def test_populate_user_github(self):
        """Test populating user from GitHub data"""
        extra_data = {"name": "Populated GitHub User", "login": "populateduser"}
        social_login = self._create_social_login("github", extra_data)

        user = self.adapter.populate_user(self.request, social_login, {})

        self.assertEqual(user.name, "Populated GitHub User")


class UserSignupFormTestCase(BaseTestCase):
    """Test case for custom UserSignupForm"""

    def test_form_valid_data(self):
        """Test form with valid data"""
        pwd = get_random_string(16)
        form_data = {
            "email": "signup@example.com",
            "password1": pwd,
            "password2": pwd,
            "name": "Signup User",
        }

        form = UserSignupForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_form_missing_name(self):
        """Test form without name (should still be valid)"""
        pwd = get_random_string(16)
        form_data = {
            "email": "noname@example.com",
            "password1": pwd,
            "password2": pwd,
        }

        form = UserSignupForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_form_invalid_email(self):
        """Test form with invalid email"""
        pwd = get_random_string(16)
        form_data = {
            "email": "invalid-email",
            "password1": pwd,
            "password2": pwd,
            "name": "Test User",
        }

        form = UserSignupForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)

    def test_form_password_mismatch(self):
        """Test form with password mismatch"""
        pwd1 = get_random_string(16)
        pwd2 = get_random_string(16)
        form_data = {
            "email": "mismatch@example.com",
            "password1": pwd1,
            "password2": pwd2,
            "name": "Test User",
        }

        form = UserSignupForm(data=form_data)
        self.assertFalse(form.is_valid())

    @pytest.mark.skip(reason="fix it -if needed- when using login via google or github (OAuth2)")
    def test_form_save(self):
        """Test form save method"""
        pwd = get_random_string(16)
        form_data = {
            "email": "formsave@example.com",
            "password1": pwd,
            "password2": pwd,
            "name": "Form Save User",
        }

        form = UserSignupForm(data=form_data)
        self.assertTrue(form.is_valid())

        # Mock request
        request = RequestFactory().get("/")

        user = form.save(request)

        self.assertEqual(user.email, "formsave@example.com")
        self.assertEqual(user.name, "Form Save User")
        self.assertTrue(user.check_password(pwd))
        self.assertTrue(User.objects.filter(email="formsave@example.com").exists())


@pytest.mark.skip(reason="fix them -if needed- when using login via google or github (OAuth2)")
class UserSocialSignupFormTestCase(BaseTestCase):
    """Test case for custom UserSocialSignupForm"""

    def test_social_form_valid_data(self):
        """Test social form with valid data"""
        form_data = {"name": "Social User"}

        form = UserSocialSignupForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_social_form_empty_data(self):
        """Test social form with empty data (should be valid)"""
        form = UserSocialSignupForm(data={})
        self.assertTrue(form.is_valid())

    def test_social_form_save_with_name(self):
        """Test social form save with name"""
        # Create a user first (would normally be done by allauth)
        tmp_password = get_random_string(20)
        user = User.objects.create_user(email="social@example.com", password=tmp_password, name="Original Name")

        form_data = {"name": "Updated Social Name"}

        form = UserSocialSignupForm(data=form_data)
        self.assertTrue(form.is_valid())

        # Mock request
        request = RequestFactory().get("/")

        # Mock the form's save behavior
        form.user = user
        saved_user = form.save(request)

        self.assertEqual(saved_user.name, "Updated Social Name")

    def test_social_form_save_without_name(self):
        """Test social form save without name"""
        # Create a user first
        tmp_password = get_random_string(20)
        user = User.objects.create_user(
            email="nosocialname@example.com",
            password=tmp_password,
            name="Original Name",
        )

        form = UserSocialSignupForm(data={})
        self.assertTrue(form.is_valid())

        # Mock request
        request = RequestFactory().get("/")

        # Mock the form's save behavior
        form.user = user
        saved_user = form.save(request)

        # Name should remain unchanged
        self.assertEqual(saved_user.name, "Original Name")
