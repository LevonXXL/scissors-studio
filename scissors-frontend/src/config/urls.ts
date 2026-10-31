/** Public origins supplied by the frontend build configuration. */
import { getThumbnailUrl, mediaAssetUrl, staticAssetUrl } from '@/utils/assetUrl';

export const SITE_URL = import.meta.env.VITE_SITE_URL;
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;
export const STATIC_URL = import.meta.env.VITE_STATIC_URL;
export const MEDIA_URL = import.meta.env.VITE_MEDIA_URL;

export const publicAssetUrl = (path: string): string => staticAssetUrl(path, STATIC_URL);
export const mediaImageUrl = (path: string): string => mediaAssetUrl(path, MEDIA_URL, API_BASE_URL);
export const mediaPreviewUrl = (path: string, width: number): string =>
  getThumbnailUrl(path, width, MEDIA_URL, API_BASE_URL);
