/**
 * Ссылка "Записаться" на конкретный салон.
 *
 * Базовый адрес — тот же, что уже используется на сайте (форма выбора
 * филиала YCLIENTS), параметр `o` в нём уже был, но оставался пустым.
 * ⚠️ Допущение: в `o` подставляется ID филиала в YCLIENTS (company_id) —
 * это выведено из структуры ссылки, не из документации. Если окажется иначе,
 * меняется только эта функция.
 */
const BOOKING_BASE_URL = 'https://n84109.yclients.com/select-city';

export function buildBookingUrl(companyId?: string | null): string {
  return `${BOOKING_BASE_URL}?o=${encodeURIComponent(companyId ?? '')}`;
}
