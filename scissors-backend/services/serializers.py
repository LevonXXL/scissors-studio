from rest_framework import serializers, viewsets

from .models import Service, ServiceCategory, ServiceSalon


class ServiceSerializer(serializers.ModelSerializer):
    url_path = serializers.CharField(source='page.url_path', read_only=True)
    duration_display = serializers.ReadOnlyField()
    image = serializers.SerializerMethodField()
    prices = serializers.SerializerMethodField()
    masters = serializers.SerializerMethodField()

    class Meta:
        model = Service
        fields = ('id', 'title', 'description', 'group_title', 'subgroup_title',
                  'conditions', 'duration_seconds', 'duration_display', 'weight',
                  'url_path', 'image', 'prices', 'masters')

    def get_image(self, obj):
        if obj.image_id:
            url = obj.image.url
        elif obj.page_id:
            picture = next((p for p in obj.page.pictures.all() if p.image_url), None)
            url = picture.image_url if picture else ''
        else:
            url = ''
        request = self.context.get('request')
        return request.build_absolute_uri(url) if url and request else url

    def _offer(self, obj):
        salon_id = self.context.get('salon_id')
        offers = obj.salon_offers.filter(is_active=True, salon__is_active=True)
        if salon_id:
            offers = offers.filter(salon_id=salon_id)
        return offers.order_by('salon_id').first()

    def get_prices(self, obj):
        offer = self._offer(obj)
        if not offer:
            return []
        order = {level: position for position, level in enumerate(
            ('universal', 'modeler', 'stylist', 'top_stylist', 'art_director',
             'nail_master', 'top_nail_master', ''))}
        prices = sorted(offer.prices.all(), key=lambda price: order.get(price.level, 8))
        # Keep the API field while older frontend builds still expect it.
        return [{'level': p.level, 'status': 'amount', 'amount': p.amount} for p in prices]

    def get_masters(self, obj):
        offer = self._offer(obj)
        if not offer:
            return []
        price_by_level = {p.level: p for p in offer.prices.all()}
        result = []
        for assignment in obj.staff_prices.filter(salon=offer.salon, master__is_active=True,
                                                   master__is_system=False,
                                                   master__is_booking_placeholder=False).select_related('master'):
            level = assignment.master.price_level
            price = price_by_level.get(level) or price_by_level.get('')
            amount = price.amount if price else None
            result.append({'id': assignment.master_id, 'name': assignment.master.name,
                           'level': level, 'amount': amount})
        return result


class ServiceCategorySerializer(serializers.ModelSerializer):
    url_path = serializers.CharField(source='page.url_path', read_only=True)
    meta_description = serializers.CharField(source='page.meta_description', read_only=True)
    image_url = serializers.SerializerMethodField()
    group_images = serializers.SerializerMethodField()
    services = serializers.SerializerMethodField()

    class Meta:
        model = ServiceCategory
        fields = ('id', 'title', 'code', 'image_url', 'group_images', 'image_path', 'weight', 'url_path', 'meta_description', 'services')

    def get_image_url(self, obj):
        if not obj.image_id:
            return ''
        url = obj.image.url
        request = self.context.get('request')
        return request.build_absolute_uri(url) if request else url

    def get_group_images(self, obj):
        if not obj.page_id:
            return []
        request = self.context.get('request')
        return [{'name': picture.alt,
                 'url': request.build_absolute_uri(picture.image_url) if request else picture.image_url}
                for picture in obj.page.pictures.all() if picture.image_url]

    def get_services(self, obj):
        salon_id = self.context.get('salon_id')
        services = obj.services.filter(is_active=True, salon_offers__is_active=True,
                                       salon_offers__salon__is_active=True)
        if salon_id:
            services = services.filter(salon_offers__salon_id=salon_id)
        services = services.select_related('page', 'image').prefetch_related('page__pictures__image')
        return ServiceSerializer(services.distinct().order_by('weight', 'id'), many=True,
                                 context=self.context).data


class ServiceCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ServiceCategory.objects.filter(is_active=True).select_related('image', 'page').prefetch_related(
        'page__pictures__image').order_by('weight', 'id')
    serializer_class = ServiceCategorySerializer

    def get_queryset(self):
        queryset = super().get_queryset().filter(services__salon_offers__is_active=True,
                                                  services__salon_offers__salon__is_active=True)
        salon_id = self.request.query_params.get('salon')
        if salon_id:
            queryset = queryset.filter(services__salon_offers__salon_id=salon_id)
        return queryset.distinct()

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['salon_id'] = self.request.query_params.get('salon')
        return context
