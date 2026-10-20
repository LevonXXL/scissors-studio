from django import forms
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserChangeForm
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.utils import timezone

from .models import PendingEmailVerification, VerifiedEmail


User = get_user_model()
admin.site.unregister(User)


class AdminUserChangeForm(UserChangeForm):
    email_verified = forms.BooleanField(label='Email подтверждён', required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            email = (self.instance.email or '').strip().casefold()
            self.fields['email_verified'].initial = bool(
                email and VerifiedEmail.objects.filter(user=self.instance, email=email).exists()
            )

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('email_verified'):
            email = (cleaned_data.get('email') or '').strip().casefold()
            try:
                validate_email(email)
            except ValidationError:
                self.add_error('email_verified', 'Укажите корректный email перед подтверждением.')
            else:
                if VerifiedEmail.objects.filter(email__iexact=email).exclude(user=self.instance).exists():
                    self.add_error('email_verified', 'Этот email уже подтверждён другим пользователем.')
        return cleaned_data


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    form = AdminUserChangeForm
    list_display = (*BaseUserAdmin.list_display, 'email_verified')

    @admin.display(boolean=True, description='Email подтверждён')
    def email_verified(self, obj):
        email = (obj.email or '').strip().casefold()
        return bool(email and VerifiedEmail.objects.filter(user=obj, email=email).exists())

    def get_fieldsets(self, request, obj=None):
        fieldsets = list(super().get_fieldsets(request, obj))
        if request.user.is_superuser and obj is not None:
            for index, (title, options) in enumerate(fieldsets):
                if 'email' in options.get('fields', ()):
                    fieldsets[index] = (title, {
                        **options,
                        'fields': (*options['fields'], 'email_verified'),
                    })
                    break
        return fieldsets

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if not request.user.is_superuser or 'email_verified' not in form.cleaned_data:
            return

        email = (obj.email or '').strip().casefold()
        if form.cleaned_data['email_verified']:
            identity = VerifiedEmail.objects.filter(user=obj).first()
            if not identity or identity.email != email:
                VerifiedEmail.objects.update_or_create(
                    user=obj,
                    defaults={'email': email, 'verified_at': timezone.now()},
                )
        else:
            VerifiedEmail.objects.filter(user=obj).delete()
        PendingEmailVerification.objects.filter(user=obj).delete()
