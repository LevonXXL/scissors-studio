import api  from '@/api/client';
import type { HomeReview, Master, PageDetail, PageListItem, PaginatedResponse, Review, ReviewSource, Salon } from '@/api/types';

export async function fetchPageByPath(urlPath: string): Promise<PageDetail> {
  const cleanPath = urlPath.replace(/^\/+|\/+$/g, '');
  const { data } = await api.get<PageDetail>(`/pages/by-path/${cleanPath}/`);
  return data;
}

export async function fetchPages(): Promise<PageListItem[]> {
  const { data } = await api.get<PaginatedResponse<PageListItem>>('/pages/');
  return data.results;
}

export async function fetchSalons(): Promise<Salon[]> {
  const { data } = await api.get<PaginatedResponse<Salon>>('/salons/');
  return data.results;
}

export async function fetchMasters(salonId?: number): Promise<Master[]> {
  const { data } = await api.get<PaginatedResponse<Master>>('/masters/', {
    params: salonId ? { salon: salonId } : {},
  });
  return data.results;
}

export async function fetchHomeReviews(limit = 20): Promise<HomeReview[]> {
  const { data } = await api.get<HomeReview[]>('/home-reviews/', {
    params: { limit },
  });
  return data;
}

export interface FetchReviewsParams {
  salon?: number;
  source?: ReviewSource;
  /** Только отзывы с фото (для главной страницы). */
  hasImages?: boolean;
  limit?: number;
}

export async function fetchReviews(params: FetchReviewsParams = {}): Promise<Review[]> {
  const { data } = await api.get<PaginatedResponse<Review> | Review[]>('/reviews/', {
    params: {
      ...(params.salon ? { salon: params.salon } : {}),
      ...(params.source ? { source: params.source } : {}),
      ...(params.hasImages ? { has_images: 'true' } : {}),
    },
  });
  // ReviewViewSet использует стандартную пагинацию DRF (в отличие от
  // /home-reviews/, где она отключена) — results может быть как объектом
  // {results: [...]}, так и голым массивом, в зависимости от настроек.
  const results = Array.isArray(data) ? data : data.results;
  return params.limit ? results.slice(0, params.limit) : results;
}

/** Салон по slug (например "moscow"). 404 от API пробрасывается как есть — вызывающий код решает, что показать. */
export async function fetchSalonBySlug(slug: string): Promise<Salon> {
  const { data } = await api.get<Salon>(`/salons/${encodeURIComponent(slug)}/`);
  return data;
}
