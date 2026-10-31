export const YCLIENTS_NETWORK_BOOKING_URL = 'https://n428078.yclients.ru';

export function salonBookingUrl(salon: { yclients_booking_url?: string } | null | undefined): string {
  return salon?.yclients_booking_url || YCLIENTS_NETWORK_BOOKING_URL;
}
