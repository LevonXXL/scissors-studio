// src/data/masters.ts
import type { SalonSlug } from '@/data/salons';

export interface Master {
  id: string;
  name: string;
  role: string;
  bio: string;
  photo: string;
  salons: SalonSlug[]; // В каких салонах работает мастер
  bookingLink: string;
  slug: string;
}

export const masters: Master[] = [
  // ==========================================
  // МАСТЕРА МОСКВЫ (Красные ворота)
  // Ссылки Yclients: n2080...
  // ==========================================
  {
    id: 'bludova-irina',
    name: 'Блудова Ирина',
    role: 'Топ-стилист',
    bio: 'Мастер с большим стажем как профессиональным, так и преподавательским. Обучает команду мастерству на основании опыта, полученного в разных странах Мира. Может найти подход к самому требовательному гостю, и к знаменитости, и к ребенку.',
    photo: 'https://static.tildacdn.com/tild3030-6561-4630-b164-303735653638/3.png',
    salons: ['moscow'],
    bookingLink: 'https://n2080161.yclients.com',
    slug: 'bludova-irina',
  },
  {
    id: 'kolchanova-marina',
    name: 'Колчанова Марина',
    role: 'Топ-стилист',
    bio: 'Тренер сборной России по парикмахерскому искусству. Специализируется на стрижках (как женских, так и мужских). Делает сложные окрашивания в ускоренном формате так, что рисунок читается профессионально и дорого.',
    photo: 'https://static.tildacdn.com/tild3033-6236-4436-b531-353061323137/1.png',
    salons: ['moscow'],
    bookingLink: 'https://n2080137.yclients.com',
    slug: 'kolchanova-marina',
  },
  {
    id: 'rekrut-polina',
    name: 'Рекрут Полина',
    role: 'Мастер-стилист',
    bio: 'Амбициозна, целеустремлённа, победитель соревнований. Педантичный мастер, которой по плечу даже самый сложный запрос по окрашиванию и стрижке. Опыт работы в Scissors — около 1,5 лет. Работает по стандартам бренда, при необходимости советуется с мастерами более высокой категории.',
    photo: 'https://static.tildacdn.com/tild3030-3230-4938-a533-613433633135/9.png',
    salons: ['moscow'],
    bookingLink: 'https://n2080107.yclients.com',
    slug: 'rekrut-polina',
  },
  {
    id: 'taryukina-yulia',
    name: 'Тарюкина Юлия',
    role: 'Мастер-модельер',
    bio: 'Мастер с опытом. Прекрасно выполняет сложные окрашивания, завивки и стрижки от классики до современных. Подберет как салонный уход, так и расскажет о домашнем уходе.',
    photo: 'https://static.tildacdn.com/tild3036-6139-4137-a139-303165363135/photo_14.png',
    salons: ['moscow'],
    bookingLink: 'https://n2080131.yclients.com',
    slug: 'taryukina-yulia',
  },
  {
    id: 'mironova-svetlana',
    name: 'Миронова Светлана',
    role: 'Топ-стилист',
    bio: 'Мастер с большим стажем. Самостоятельно выстраивает путь к желаемому образу клиента. Обучает команду и регулярно повышает квалификацию во внутренних и внешних школах. (Прим.: в HTML Tilda была ошибка верстки, где её имя стояло рядом с ролью "Старший Мастер маникюра", но описание и контекст указывают на парикмахера-топа).',
    photo: 'https://static.tildacdn.com/tild3030-6264-4433-a233-373637633734/see-plus-SeKz_7CAQYY.png', // Заменить на реальное фото Светланы, если это фото Агаты
    salons: ['moscow'],
    bookingLink: 'https://n2080XXX.yclients.com', // TODO: уточнить реальную ссылку Yclients для Светланы
    slug: 'mironova-svetlana',
  },
  {
    id: 'rysovets-oksana',
    name: 'Рысовец Оксана',
    role: 'Топ-стилист',
    bio: 'Опыт работы в Scissors — более 3 лет. Самостоятельно выстраивает путь к желаемому образу клиента. Обучает команду и регулярно повышает квалификацию во внутренних и внешних школах. (Прим.: в исходном HTML Tilda описании Оксаны случайно продублировался текст основателя, здесь восстановлено стандартное описание Топ-стилиста).',
    photo: 'https://static.tildacdn.com/tild3030-6264-4433-a233-373637633734/see-plus-SeKz_7CAQYY.png', // TODO: вставить реальную ссылку на фото Оксаны из tilda_assets
    salons: ['moscow'],
    bookingLink: 'https://n2080XXX.yclients.com', // TODO: уточнить реальную ссылку Yclients для Оксаны
    slug: 'rysovets-oksana',
  },

  // ==========================================
  // МАСТЕРА ЗЕЛЕНОГРАДА (17 район)
  // Ссылки Yclients: n84109
  // ==========================================
  {
    id: 'oskina-agata',
    name: 'Оськина Агата',
    role: 'Мастер-модельер',
    bio: 'Человек-позитив с отличным чувством юмора. Опытный специалист, который чётко чувствует ваш запрос. Сложные случаи в окрашивании — её конёк.',
    photo: 'https://static.tildacdn.com/tild3030-6264-4433-a233-373637633734/see-plus-SeKz_7CAQYY.png',
    salons: ['zelenograd'],
    bookingLink: 'https://n84109.yclients.com/select-city?o=',
    slug: 'oskina-agata',
  },
  {
    id: 'stets-mikhail',
    name: 'Стець Михаил',
    role: 'Арт-директор',
    bio: 'Идейный вдохновитель и основатель всего проекта Scissors. Тренер команды и практикующий мастер с опытом более 25 лет. За плечами большой международный опыт обучений и практики. Чемпион Москвы и России, международный судья и преподаватель.',
    photo: 'https://static.tildacdn.com/tild3037-3166-4935-a439-316366616235/3.png',
    salons: ['moscow', 'zelenograd'], // Основатель принимает в обоих салонах
    bookingLink: 'https://n84109.yclients.com/select-city?o=',
    slug: 'stets-mikhail',
  },
];

// Вспомогательная функция для получения мастеров по салону
export const getMastersBySalon = (salonSlug: SalonSlug): Master[] => {
  return masters.filter(master => master.salons.includes(salonSlug));
};

// Вспомогательная функция для получения мастера по slug
export const getMasterBySlug = (slug: string): Master | undefined => {
  return masters.find(master => master.slug === slug);
};
