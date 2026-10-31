/** Resolve public/ assets and Django media independently. */
export function staticAssetUrl(path: string, baseUrl?: string): string {
  const base = (
    baseUrl ||
    import.meta.env?.VITE_STATIC_URL ||
    ''
  ).replace(/\/+$/, '');

  if (
    !path ||
    !base ||
    /^(?:[a-z][\w+.-]*:)?\/\//i.test(path) ||
    /^(?:data|blob):/i.test(path)
  ) {
    return path;
  }

  return `${base}/${path.replace(/^\/+/, '')}`;
}

export function mediaAssetUrl(source: string, mediaBaseUrl: string, apiBaseUrl = ''): string {
  if (!source || !mediaBaseUrl) return source;

  try {
    const media = new URL(mediaBaseUrl);
    const apiOrigin = apiBaseUrl ? new URL(apiBaseUrl).origin : '';
    const absolute = /^(?:[a-z][\w+.-]*:)?\/\//i.test(source);
    const image = new URL(source, 'https://relative.invalid');
    if (absolute && image.origin !== media.origin && image.origin !== apiOrigin) return source;

    const mediaPath = media.pathname.endsWith('/') ? media.pathname : `${media.pathname}/`;
    const originalPath = image.pathname;
    const relativePath = originalPath.startsWith(mediaPath)
      ? originalPath.slice(mediaPath.length)
      : originalPath.startsWith('/media/')
        ? originalPath.slice('/media/'.length)
        : !absolute && originalPath.startsWith('/filer_public/')
          ? originalPath.slice(1)
          : null;
    if (relativePath === null) return source;

    return new URL(`${relativePath}${image.search}${image.hash}`, media).href;
  } catch {
    return source;
  }
}

/** Serve Filer previews from the same host that serves Django media. */
export function getThumbnailUrl(imageUrl: string, width: number, mediaBaseUrl: string, apiBaseUrl = ''): string {
  const original = mediaAssetUrl(imageUrl, mediaBaseUrl, apiBaseUrl);
  if (!original || !Number.isInteger(width) || width < 1 || width > 2000) return original;

  try {
    const media = new URL(mediaBaseUrl);
    const image = new URL(original, media.origin);
    const mediaPath = media.pathname.endsWith('/') ? media.pathname : `${media.pathname}/`;
    if (image.origin !== media.origin || !image.pathname.startsWith(`${mediaPath}filer_public/`)) {
      return original;
    }

    const path = image.pathname.slice(mediaPath.length);
    return `${media.origin}/thumbnail/${width}/${path}`;
  } catch {
    return original;
  }
}
