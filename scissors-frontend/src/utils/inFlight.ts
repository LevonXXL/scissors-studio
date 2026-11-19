const pendingByOwner = new WeakMap<object, Map<string, Promise<unknown>>>();

/** Share concurrent loads within one store instance without serializing promises into SSR state. */
export function dedupeInFlight<T>(
  owner: object,
  key: string,
  load: () => Promise<T>,
): Promise<T> {
  let pending = pendingByOwner.get(owner);
  if (!pending) {
    pending = new Map();
    pendingByOwner.set(owner, pending);
  }

  const existing = pending.get(key);
  if (existing) return existing as Promise<T>;

  const request = Promise.resolve().then(load);
  pending.set(key, request);

  const clear = () => {
    if (pending?.get(key) === request) pending.delete(key);
    if (pending?.size === 0) pendingByOwner.delete(owner);
  };
  void request.then(clear, clear);

  return request;
}
