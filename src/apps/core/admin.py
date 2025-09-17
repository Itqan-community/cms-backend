from allauth.account.models import EmailAddress, EmailConfirmation
from allauth.socialaccount.models import SocialAccount, SocialApp, SocialToken
from django.contrib import admin
from django.contrib.sites.models import Site

admin.site.unregister([Site, EmailAddress, EmailConfirmation, SocialAccount, SocialApp, SocialToken])