import api  from '@/api/client';

export interface SearchHit {
  id: string;
  type: 'page' | 'master' | 'salon' | 'category' | 'service';
  title: string;
  content: string;
  url: string;
}

export interface SearchResponse {
  data: SearchHit[];
  pagination: { page: number; pageSize: number; totalCount: number };
}

export async function fetchSearch(query: string, page = 1, pageSize = 30): Promise<SearchResponse> {
  const { data } = await api.get<SearchResponse>('/search', {
    params: {
      query,
      'pagination.page': page,
      'pagination.pageSize': pageSize,
    },
  });
  return data;
}

export interface CatalogueCategorySummary {
  id: number;
  title: string;
  code: string;
  image_url: string;
  image_path: string;
  url_path: string;
  meta_description: string;
}

export async function fetchCatalogueCategories(): Promise<CatalogueCategorySummary[]> {
  const { data } = await api.get<PaginatedResponse<CatalogueCategorySummary> | CatalogueCategorySummary[]>('/service-categories/');
  return Array.isArray(data) ? data : data.results;
}
import type { HomeReview, Master, PageDetail, PageListItem, PaginatedResponse, Review, ReviewSource, Salon } from '@/api/types';

export async function fetchPageByPath(urlPath: string): Promise<PageDetail> {
  const cleanPath = urlPath.replace(/^\/+|\/+$/g, '');
  const suffix = cleanPath ? `${cleanPath}/` : '';
  const { data } = await api.get<PageDetail>(`/pages/by-path/${suffix}`);
  return data;
}

export async function fetchPages(): Promise<PageListItem[]> {
  const { data } = await api.get<PaginatedResponse<PageListItem>>('/pages/');
  return data.results;
}

export async function fetchSalons(): Promise<Salon[]> {
  const salons: Salon[] = [];
  let page = 1;
  while (true) {
    const { data } = await api.get<PaginatedResponse<Salon>>('/salons/', { params: { page } });
    salons.push(...data.results);
    if (!data.next) return salons;
    page += 1;
  }
}

export async function fetchSalonBySlug(slug: string): Promise<Salon> {
  const { data } = await api.get<Salon>(`/salons/by-slug/${encodeURIComponent(slug)}/`);
  return data;
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
  limit?: number;
  withImages?: boolean;
}

export async function fetchReviews(params: FetchReviewsParams = {}): Promise<Review[]> {
  const results: Review[] = [];
  let page = 1;
  while (true) {
    const { data } = await api.get<PaginatedResponse<Review> | Review[]>('/reviews/', {
      params: {
        ...(params.salon ? { salon: params.salon } : {}),
        ...(params.source ? { source: params.source } : {}),
        ...(params.withImages ? { with_images: 1 } : {}),
        page,
      },
    });
    results.push(...(Array.isArray(data) ? data : data.results));
    if (Array.isArray(data) || !params.salon || !data.next) break;
    page += 1;
  }
  return params.limit ? results.slice(0, params.limit) : results;
}

export interface AuthResult {
  access: string;
  is_staff: boolean;
  phone: string;
  phones: string[];
  email: string;
  pending_email: string;
  has_password: boolean;
  push_enabled: boolean;
}

export interface AuthProfile {
  is_staff: boolean;
  phone: string;
  phones: string[];
  email: string;
  pending_email: string;
  has_password: boolean;
  push_enabled: boolean;
}

export async function createFeedbackRequest(values: { name: string; phone: string; message: string }): Promise<void> {
  await api.post('/feedback/', values);
}

export async function getPushPublicKey(): Promise<string> {
  const { data } = await api.get<{ public_key: string }>('/push/public-key/');
  return data.public_key;
}

export async function setPushPreference(enabled: boolean): Promise<void> {
  await api.put('/push/preferences/', { enabled });
}

export async function savePushSubscription(subscription: PushSubscription): Promise<void> {
  await api.post('/push/subscriptions/', subscription.toJSON());
}

export async function deletePushSubscription(subscription: PushSubscription): Promise<void> {
  await api.delete('/push/subscriptions/', { data: subscription.toJSON() });
}

export async function requestAuthCode(phone: string): Promise<void> {
  await api.post('/auth/request-code/', { phone });
}

export async function verifyAuthCode(phone: string, code: string): Promise<AuthResult> {
  const { data } = await api.post<AuthResult>('/auth/verify-code/', { phone, code });
  return data;
}

export async function verifyProfilePhone(phone: string, code: string): Promise<AuthProfile> {
  const { data } = await api.post<AuthProfile>('/auth/phone/verify/', { phone, code });
  return data;
}

export async function loginWithPassword(phone: string, password: string): Promise<AuthResult> {
  const { data } = await api.post<AuthResult>('/auth/login-password/', { phone, password });
  return data;
}

export async function loginWithEmail(email: string, password: string): Promise<AuthResult> {
  const { data } = await api.post<AuthResult>('/auth/login-email/', { email, password });
  return data;
}

export async function requestEmailVerification(email: string, currentPassword = ''): Promise<void> {
  await api.post('/auth/email/request-verification/', { email, current_password: currentPassword });
}

export async function verifyEmail(token: string): Promise<void> {
  await api.post('/auth/email/verify/', { token });
}

export async function getAuthProfile(): Promise<AuthProfile> {
  const { data } = await api.get<AuthProfile>('/auth/me/');
  return data;
}

export interface BookingOptions {
  services: { id: number; title: string; category: string; master_ids: number[] }[];
  masters: { id: number; name: string; slug: string }[];
}

export interface BookingRequestInput {
  salon: number;
  service_ids: number[];
  preferred_master: number | null;
  requested_start: string;
  requested_end?: string | null;
  name: string;
  phone?: string;
  comment?: string;
}

export async function fetchBookingOptions(salonId: number): Promise<BookingOptions> {
  const { data } = await api.get<BookingOptions>('/booking-options/', { params: { salon: salonId } });
  return data;
}

export async function createBookingRequest(values: BookingRequestInput): Promise<{ id: number; status: string; detail: string }> {
  const { data } = await api.post<{ id: number; status: string; detail: string }>('/booking-requests/', values);
  return data;
}

export interface MyBooking {
  id: number;
  salon: string;
  master: string | null;
  services: string;
  status: 'pending' | 'confirmed' | 'cancelled' | 'completed' | 'no_show';
  requested_start: string | null;
  requested_end: string | null;
  start_datetime: string | null;
  end_datetime: string | null;
}

export async function fetchMyBookings(period: 'future' | 'past', page = 1): Promise<PaginatedResponse<MyBooking>> {
  const { data } = await api.get<PaginatedResponse<MyBooking>>('/booking-requests/mine/', { params: { period, page } });
  return data;
}

export async function setAuthPassword(newPassword: string): Promise<void> {
  await api.post('/auth/set-password/', { new_password: newPassword });
}

export async function changeAuthPassword(currentPassword: string, newPassword: string): Promise<void> {
  await api.post('/auth/change-password/', { current_password: currentPassword, new_password: newPassword });
}
