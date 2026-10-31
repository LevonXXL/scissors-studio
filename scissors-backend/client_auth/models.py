from django.conf import settings
from django.db import models


class VerifiedPhone(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='verified_phones')
    phone = models.CharField(max_length=12, unique=True)
    verified_at = models.DateTimeField()


class VerifiedEmail(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='verified_email')
    email = models.EmailField(max_length=254, unique=True)
    verified_at = models.DateTimeField()


class PendingEmailVerification(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='pending_email_verification')
    email = models.EmailField(max_length=254)
    token_hash = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField()
    expires_at = models.DateTimeField()


class PhoneVerificationSession(models.Model):
    phone = models.CharField(max_length=12, unique=True)
    started_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    last_requested_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    completed_at = models.DateTimeField(null=True, blank=True)


class PhoneCode(models.Model):
    phone = models.CharField(max_length=12)
    session = models.ForeignKey(PhoneVerificationSession, on_delete=models.CASCADE, related_name='codes')
    code_hash = models.CharField(max_length=255)
    expires_at = models.DateTimeField()
    requested_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)


class AuthRateLimit(models.Model):
    key = models.CharField(max_length=64, unique=True)
    window_start = models.DateTimeField()
    count = models.PositiveIntegerField(default=0)
