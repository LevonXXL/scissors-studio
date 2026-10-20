from django.conf import settings
from django.db import transaction
from django.http import FileResponse
from django.shortcuts import render
from pathlib import Path
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import PushPreference, PushSubscription
from .push import notify_new_feedback, push_configured
from .serializers import FeedbackRequestSerializer, PushPreferenceSerializer, PushSubscriptionSerializer


class FeedbackRequestView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = FeedbackRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            feedback = serializer.save(user=request.user if request.user.is_authenticated else None)
            transaction.on_commit(lambda: notify_new_feedback(feedback))
        return Response({'id': feedback.pk}, status=status.HTTP_201_CREATED)


class PushPublicKeyView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        if not push_configured():
            return Response({'detail': 'Push-уведомления пока недоступны.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response({'public_key': settings.WEB_PUSH_VAPID_PUBLIC_KEY})


class PushPreferenceView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        enabled = PushPreference.objects.filter(user=request.user, enabled=True).exists()
        return Response({'enabled': enabled})

    def put(self, request):
        serializer = PushPreferenceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        enabled = serializer.validated_data['enabled']
        with transaction.atomic():
            PushPreference.objects.update_or_create(user=request.user, defaults={'enabled': enabled})
            if not enabled:
                PushSubscription.objects.filter(user=request.user).delete()
        return Response({'enabled': enabled})


class PushSubscriptionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not push_configured():
            return Response({'detail': 'Push-уведомления пока недоступны.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        serializer = PushSubscriptionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if not PushPreference.objects.filter(user=request.user, enabled=True).exists():
            return Response({'detail': 'Сначала включите push-сообщения в профиле.'}, status=status.HTTP_403_FORBIDDEN)
        endpoint = serializer.validated_data['endpoint']
        keys = serializer.validated_data['keys']
        with transaction.atomic():
            subscription, created = PushSubscription.objects.select_for_update().get_or_create(
                endpoint=endpoint,
                defaults={'user': request.user, **keys},
            )
            if subscription.user_id != request.user.pk:
                return Response({'detail': 'Подписка уже привязана к другой учётной записи.'}, status=status.HTTP_409_CONFLICT)
            if not created:
                subscription.p256dh = keys['p256dh']
                subscription.auth = keys['auth']
                subscription.save(update_fields=['p256dh', 'auth', 'updated_at'])
        return Response(status=status.HTTP_204_NO_CONTENT)

    def delete(self, request):
        serializer = PushSubscriptionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        PushSubscription.objects.filter(user=request.user, endpoint=serializer.validated_data['endpoint']).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


def admin_push_settings(request):
    from django.contrib import admin

    context = admin.site.each_context(request)
    context['title'] = 'Мои настройки'
    return render(request, 'communications/admin_push_settings.html', context)


def admin_push_service_worker(request):
    source = Path(__file__).parent / 'static' / 'communications' / 'admin_push_sw.js'
    response = FileResponse(source.open('rb'), content_type='application/javascript')
    response['Cache-Control'] = 'no-cache'
    response['Service-Worker-Allowed'] = '/admin/'
    return response
