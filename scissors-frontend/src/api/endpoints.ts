import api  from '@/api/client';
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
  email: string;
  pending_email: string;
  has_password: boolean;
  push_enabled: boolean;
}

export interface AuthProfile {
  is_staff: boolean;
  phone: string;
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

export async function setAuthPassword(newPassword: string): Promise<void> {
  await api.post('/auth/set-password/', { new_password: newPassword });
}

export async function changeAuthPassword(currentPassword: string, newPassword: string): Promise<void> {
  await api.post('/auth/change-password/', { current_password: currentPassword, new_password: newPassword });
}
