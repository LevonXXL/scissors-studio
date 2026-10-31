from django.urls import path

from .views import BookingOptionsView, BookingRequestView, MyBookingsView


urlpatterns = [
    path('booking-options/', BookingOptionsView.as_view(), name='booking-options'),
    path('booking-requests/', BookingRequestView.as_view(), name='booking-request'),
    path('booking-requests/mine/', MyBookingsView.as_view(), name='my-bookings'),
]
