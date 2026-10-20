from django.urls import path

from .views import FeedbackRequestView, PushPreferenceView, PushPublicKeyView, PushSubscriptionView

urlpatterns = [
    path('feedback/', FeedbackRequestView.as_view(), name='feedback-create'),
    path('push/public-key/', PushPublicKeyView.as_view(), name='push-public-key'),
    path('push/preferences/', PushPreferenceView.as_view(), name='push-preferences'),
    path('push/subscriptions/', PushSubscriptionView.as_view(), name='push-subscriptions'),
]
