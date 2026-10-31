from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .manticore import ManticoreClient, ManticoreError


class SearchView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        query = request.query_params.get('query', '').strip()
        if len(query) < 3 or len(query) > 200:
            return Response({'detail': 'Введите запрос длиной от 3 до 200 символов.'}, status=400)

        try:
            page = int(request.query_params.get('pagination.page', '1'))
            page_size = int(request.query_params.get('pagination.pageSize', '30'))
        except (TypeError, ValueError):
            return Response({'detail': 'Некорректная пагинация.'}, status=400)
        if page < 1 or page_size < 1 or page_size > 100 or page * page_size > 10000:
            return Response({'detail': 'Некорректная пагинация.'}, status=400)

        try:
            results, total = ManticoreClient().search(query, page, page_size)
        except ManticoreError:
            return Response({'detail': 'Поиск временно недоступен.'}, status=503)

        return Response({
            'data': results,
            'pagination': {'page': page, 'pageSize': page_size, 'totalCount': total},
        })
