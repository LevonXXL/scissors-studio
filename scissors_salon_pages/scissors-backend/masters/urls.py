from rest_framework.routers import DefaultRouter

from .views import MasterViewSet

router = DefaultRouter()
router.register('masters', MasterViewSet, basename='master')

urlpatterns = router.urls
