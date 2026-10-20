from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r'reviews', views.ReviewViewSet, basename='review')
router.register(r'home-reviews', views.HomeReviewViewSet, basename='home-review')

urlpatterns = [
    path('', include(router.urls)),
]