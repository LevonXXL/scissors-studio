/** Build a thumbnail URL only for Django Filer images on the configured media host. */
export function getThumbnailUrl(imageUrl: string, width: number, mediaBaseUrl: string): string {
  if (!imageUrl || !Number.isInteger(width) || width < 1 || width > 2000) return imageUrl;

  try {
    const media = new URL(mediaBaseUrl);
    const image = new URL(imageUrl, media.origin);
    const mediaPath = media.pathname.endsWith('/') ? media.pathname : `${media.pathname}/`;
    if (image.origin !== media.origin || !image.pathname.startsWith(`${mediaPath}filer_public/`)) {
      return imageUrl;
    }

    const path = image.pathname.slice(mediaPath.length);
    return `${media.origin}/thumbnail/${width}/${path}`;
  } catch {
    return imageUrl;
  }
}
