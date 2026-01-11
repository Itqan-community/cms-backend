from allauth.account.models import EmailAddress, EmailConfirmation
from django.contrib import admin
from django.contrib.auth.models import Group
from django.contrib.sites.models import Site
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

admin.site.unregister(
    [
        Site,
        EmailAddress,
        EmailConfirmation,
        BlacklistedToken,
        OutstandingToken,
        Group,
    ]
)
