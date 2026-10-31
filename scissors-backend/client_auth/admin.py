from django import forms
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserChangeForm
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.utils import timezone

from .models import PendingEmailVerification, VerifiedEmail, VerifiedPhone
from .services import normalize_phone


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


class VerifiedPhoneInlineForm(forms.ModelForm):
    phone = forms.CharField(label='Телефон', max_length=32)

    class Meta:
        model = VerifiedPhone
        fields = ('phone',)

    def clean_phone(self):
        try:
            phone = normalize_phone(self.cleaned_data['phone'])
        except ValidationError as exc:
            raise forms.ValidationError(exc.messages) from exc
        if User.objects.filter(username=phone).exclude(pk=self.instance.user_id).exists():
            raise forms.ValidationError('Этот номер уже используется другим пользователем.')
        return phone


class VerifiedPhoneInline(admin.TabularInline):
    model = VerifiedPhone
    form = VerifiedPhoneInlineForm
    extra = 1
    fields = ('phone', 'confirmation_date')
    readonly_fields = ('confirmation_date',)
    verbose_name = 'Подтверждённый телефон'
    verbose_name_plural = 'Подтверждённые телефоны'

    @admin.display(description='Подтверждён')
    def confirmation_date(self, obj):
        return obj.verified_at if obj.pk else 'При сохранении'


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    form = AdminUserChangeForm
    inlines = (VerifiedPhoneInline,)
    list_display = (*BaseUserAdmin.list_display, 'phone_number', 'email_verified')
    search_fields = (*BaseUserAdmin.search_fields, 'verified_phones__phone')

    @admin.display(description='Телефон')
    def phone_number(self, obj):
        return ', '.join(identity.phone for identity in obj.verified_phones.all()) or '—'

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('verified_phones')

    def get_inline_instances(self, request, obj=None):
        if not request.user.is_superuser or obj is None:
            return []
        return super().get_inline_instances(request, obj)

    def get_readonly_fields(self, request, obj=None):
        fields = super().get_readonly_fields(request, obj)
        if obj is not None and not request.user.is_superuser:
            return (*fields, 'phone_number')
        return fields

    @admin.display(boolean=True, description='Email подтверждён')
    def email_verified(self, obj):
        email = (obj.email or '').strip().casefold()
        return bool(email and VerifiedEmail.objects.filter(user=obj, email=email).exists())

    def get_fieldsets(self, request, obj=None):
        fieldsets = list(super().get_fieldsets(request, obj))
        if obj is not None:
            for index, (title, options) in enumerate(fieldsets):
                if 'email' in options.get('fields', ()):
                    fieldsets[index] = (title, {
                        **options,
                        'fields': (*options['fields'], *(
                            ('email_verified',) if request.user.is_superuser else ('phone_number',)
                        )),
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

    def save_formset(self, request, form, formset, change):
        if formset.model is not VerifiedPhone:
            return super().save_formset(request, form, formset, change)
        for instance in formset.save(commit=False):
            if not instance.pk:
                instance.verified_at = timezone.now()
            instance.save()
        for instance in formset.deleted_objects:
            instance.delete()
        formset.save_m2m()
