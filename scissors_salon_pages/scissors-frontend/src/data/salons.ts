export interface SalonInfo {
  slug: string;
  city: string;
  cityPrepositional: string; // "в Москве" / "в Зеленограде"
  shortName: string;
  phone: string;
  phoneRaw: string;
  hours: string;
  address: string;
  mapLink: string;
  telegram: string;
  whatsapp: string;
}

// Реальные данные — дословно с текущего сайта (подтверждено дампом
// studio.scissors.group, включая tel:/telegram/whatsapp/Яндекс.Карты ссылки).
export const salons: SalonInfo[] = [
  {
    slug: 'moscow',
    city: 'Москва',
    cityPrepositional: 'в Москве',
    shortName: 'Москва Красные ворота',
    phone: '+7 (926) 071-71-63',
    phoneRaw: '+79260717163',
    hours: 'Ежедневно 10:00 — 22:00',
    address: 'Большой Козловский переулок, 11/4',
    mapLink: 'https://yandex.ru/maps/-/CLcfFPLP',
    telegram: 'https://t.me/+79260717163',
    whatsapp: 'https://wa.me/79260717163',
  },
  {
    slug: 'zelenograd',
    city: 'Зеленоград',
    cityPrepositional: 'в Зеленограде',
    shortName: 'Зеленоград 17 район',
    phone: '+7 (926) 729-79-89',
    phoneRaw: '+79267297989',
    hours: 'Ежедневно 10:00 — 21:00',
    address: 'Георгиевский проспект, 33А, к.2',
    mapLink: 'https://yandex.ru/maps/-/CLcfFQpf',
    telegram: 'https://t.me/+79267297989',
    whatsapp: 'https://wa.me/79267297989',
  },
];

export type SalonSlug = 'moscow' | 'zelenograd';
