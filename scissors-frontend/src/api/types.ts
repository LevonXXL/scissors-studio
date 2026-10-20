// Соответствуют сериализаторам Django (pages/salons/masters serializers.py)

export interface PagePicture {
  id: number;
  image: string;
  alt: string;
  position: number;
}

export interface PageListItem {
  id: number;
  title: string;
  title_tag: string;
  meta_description: string;
  url: string;
  url_path: string;
  parent: number | null;
  position: number;
}

export interface PageDetail {
  id: number;
  title: string;
  title_tag: string;
  content: string;
  meta_title: string;
  meta_description: string;
  url: string;
  url_path: string;
  parent: number | null;
  pictures: PagePicture[];
}

export interface SalonPhoto {
  id: number;
  image: string;
  position: number;
}

export interface Salon {
  id: number;
  slug: string;
  page: PageDetail | null;
  name: string;
  address: string;
  latitude: string;
  longitude: string;
  coordinates: [number, number];
  phone: string;
  working_hours: string;
  description: string;
  logo: string | null;
  photos: SalonPhoto[];
  position: number;
}

export interface SalonBrief {
  id: number;
  name: string;
}

export interface Master {
  id: number;
  slug: string;
  name: string;
  specialization: string;
  category_display: string;
  photo: string | null;
  bio: string;
  salon_details: SalonBrief[];
}

export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface HomeReview {
  id: number;
  type: 'text' | 'video';
  author: string;
  text: string;
  rating: number | null;
  workImage: string;
  review_url: string;
}

export type ReviewSource = 1 | 2 | 3 | 4 | 5 | 99;

// Совпадает с Review.SOURCE_CHOICES на бэкенде (reviews/models.py) — если
// там добавят новую площадку, отразить и здесь.
export const REVIEW_SOURCE_LABELS: Record<ReviewSource, string> = {
  1: 'Яндекс.Карты',
  2: '2ГИС',
  3: 'Zoon',
  4: 'Google',
  5: 'Flamp',
  99: 'Другое',
};

export interface ReviewImage {
  preview?: string;
  image?: string;
}

export interface Review {
  id: number;
  salon: number;
  salon_name: string;
  source: ReviewSource;
  source_display: string;
  author: string;
  text: string;
  rating: number | null;
  review_date: string;
  review_url: string;
  reply_text: string;
  reply_date: string | null;
  has_images: boolean;
  images: ReviewImage[];
  has_videos: boolean;
  videos: unknown[];
}
