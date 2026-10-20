from rest_framework.routers import DefaultRouter

from .views import ServiceCategoryViewSet

router = DefaultRouter()
router.register('service-categories', ServiceCategoryViewSet, basename='service-category')

urlpatterns = router.urls
