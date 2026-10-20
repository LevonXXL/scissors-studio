from django.urls import path

from .views import ChangePasswordView, LoginEmailView, LoginPasswordView, MeView, RequestCodeView, RequestEmailVerificationView, SetPasswordView, VerifyCodeView, VerifyEmailView

urlpatterns = [
    path('request-code/', RequestCodeView.as_view(), name='auth-request-code'),
    path('verify-code/', VerifyCodeView.as_view(), name='auth-verify-code'),
    path('login-password/', LoginPasswordView.as_view(), name='auth-login-password'),
    path('login-email/', LoginEmailView.as_view(), name='auth-login-email'),
    path('email/request-verification/', RequestEmailVerificationView.as_view(), name='auth-email-request-verification'),
    path('email/verify/', VerifyEmailView.as_view(), name='auth-email-verify'),
    path('me/', MeView.as_view(), name='auth-me'),
    path('set-password/', SetPasswordView.as_view(), name='auth-set-password'),
    path('change-password/', ChangePasswordView.as_view(), name='auth-change-password'),
]
