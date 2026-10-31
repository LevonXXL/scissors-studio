import ipaddress
import re
from urllib.parse import urlsplit

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from client_auth.services import normalize_phone

from .models import FeedbackRequest


class FeedbackRequestSerializer(serializers.ModelSerializer):
    name = serializers.CharField(max_length=100, min_length=2, trim_whitespace=True)
    phone = serializers.CharField(max_length=254, trim_whitespace=True)
    message = serializers.CharField(max_length=4000, min_length=2, trim_whitespace=True)

    class Meta:
        model = FeedbackRequest
        fields = ['id', 'name', 'phone', 'message', 'created_at']
        read_only_fields = ['id', 'created_at']

    def validate_phone(self, value):
        if '@' in value:
            return serializers.EmailField(max_length=254).run_validation(value)
        try:
            return normalize_phone(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc


class SubscriptionKeysSerializer(serializers.Serializer):
    p256dh = serializers.CharField(max_length=512)
    auth = serializers.CharField(max_length=256)

    def validate(self, attrs):
        for value in attrs.values():
            if not re.fullmatch(r'[A-Za-z0-9_-]+={0,2}', value):
                raise serializers.ValidationError('Некорректные ключи push-подписки.')
        return attrs


class PushSubscriptionSerializer(serializers.Serializer):
    endpoint = serializers.URLField(max_length=2048)
    keys = SubscriptionKeysSerializer()

    def validate_endpoint(self, value):
        url = urlsplit(value)
        host = url.hostname or ''
        if url.scheme != 'https' or not host or url.username or url.password or url.fragment or host == 'localhost':
            raise serializers.ValidationError('Некорректный адрес push-подписки.')
        try:
            ipaddress.ip_address(host)
        except ValueError:
            pass
        else:
            raise serializers.ValidationError('Некорректный адрес push-подписки.')
        return value


class PushPreferenceSerializer(serializers.Serializer):
    enabled = serializers.BooleanField()
