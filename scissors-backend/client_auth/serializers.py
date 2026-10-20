from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .services import normalize_phone


class PhoneSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=32)

    def validate_phone(self, value):
        try:
            return normalize_phone(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc


class VerifyCodeSerializer(PhoneSerializer):
    code = serializers.RegexField(r'^\d{6}$', max_length=6, min_length=6, write_only=True)


class LoginPasswordSerializer(PhoneSerializer):
    password = serializers.CharField(write_only=True, trim_whitespace=False)


class EmailSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)

    def validate_email(self, value):
        return value.strip().casefold()


class LoginEmailSerializer(EmailSerializer):
    password = serializers.CharField(write_only=True, trim_whitespace=False)


class RequestEmailVerificationSerializer(EmailSerializer):
    current_password = serializers.CharField(write_only=True, trim_whitespace=False, required=False, allow_blank=True)


class VerifyEmailSerializer(serializers.Serializer):
    token = serializers.RegexField(r'^[A-Za-z0-9_-]{30,128}$', write_only=True)


class SetPasswordSerializer(serializers.Serializer):
    new_password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate_new_password(self, value):
        try:
            validate_password(value, self.context['request'].user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc
        return value


class ChangePasswordSerializer(SetPasswordSerializer):
    current_password = serializers.CharField(write_only=True, trim_whitespace=False)
