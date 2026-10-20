from django.db import transaction
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import VerifiedEmail, VerifiedPhone
from .serializers import ChangePasswordSerializer, LoginEmailSerializer, LoginPasswordSerializer, PhoneSerializer, RequestEmailVerificationSerializer, SetPasswordSerializer, VerifyCodeSerializer, VerifyEmailSerializer
from .services import auth_response, email_password_login, password_login, profile_response, request_code, request_email_verification, verify_code, verify_email_token


def profile_user(request):
    user = request.user
    if not user.is_active or not (
        user.is_staff or VerifiedPhone.objects.filter(user=user).exists() or VerifiedEmail.objects.filter(user=user).exists()
    ):
        raise PermissionDenied('Профиль недоступен.')
    return user


class RequestCodeView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = PhoneSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if not request_code(request, serializer.validated_data['phone']):
            return Response({'detail': 'Отправка SMS временно недоступна.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response({'detail': 'В режиме разработки код доступен в журнале сервера.'}, status=status.HTTP_202_ACCEPTED)


class VerifyCodeView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = VerifyCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = verify_code(request, **serializer.validated_data)
        return Response(auth_response(user))


class LoginPasswordView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = LoginPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = password_login(request, **serializer.validated_data)
        return Response(auth_response(user))


class LoginEmailView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = LoginEmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = email_password_login(request, **serializer.validated_data)
        return Response(auth_response(user))


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(profile_response(profile_user(request)))


class RequestEmailVerificationView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = RequestEmailVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        request_email_verification(request, profile_user(request), **serializer.validated_data)
        return Response({'detail': 'Если адрес доступен, ссылка подтверждения отправлена.'}, status=status.HTTP_202_ACCEPTED)


class VerifyEmailView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = VerifyEmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        verify_email_token(serializer.validated_data['token'])
        return Response({'detail': 'Email подтверждён.'})


class SetPasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = SetPasswordSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            user = profile_user(request)
            user = type(user).objects.select_for_update().get(pk=user.pk)
            if user.has_usable_password():
                raise ValidationError({'detail': 'Пароль уже установлен. Используйте смену пароля.'})
            user.set_password(serializer.validated_data['new_password'])
            user.save(update_fields=['password'])
        return Response({'detail': 'Пароль установлен.'})


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            user = profile_user(request)
            user = type(user).objects.select_for_update().get(pk=user.pk)
            if not user.has_usable_password() or not user.check_password(serializer.validated_data['current_password']):
                raise ValidationError({'detail': 'Не удалось сменить пароль.'})
            user.set_password(serializer.validated_data['new_password'])
            user.save(update_fields=['password'])
        return Response({'detail': 'Пароль изменён.'})
