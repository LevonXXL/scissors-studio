// src/data/home.ts

export interface ReviewItem {
  id: string;
  type: 'video' | 'text';
  youtubeId?: string;
  videoThumbnail?: string;
  author?: string;
  text?: string;
  workImage?: string;
}

export const reviews: ReviewItem[] = [
  {
    id: 'v1',
    type: 'video',
    youtubeId: 'kJr_UG4dQgc',
    videoThumbnail: '/img/video-thumbs/video-1.png',
  },
  {
    id: 't1',
    type: 'text',
    author: 'Маргарита',
    text: 'Делала мелирование с акцентами и окрашивание — результат превзошёл ожидания! Волосы просто супер-качества: цвет идеальный, структура ухоженная.',
    workImage: '/img/reviews/avatar-1.png',
  },
  {
    id: 'v2',
    type: 'video',
    youtubeId: 'mBow4dVdpkI',
    videoThumbnail: '/img/video-thumbs/video-2.png',
  },
  {
    id: 't2',
    type: 'text',
    author: 'Елена',
    text: 'Самый лучший салон красоты! Прекрасное обслуживание! Профессиональные мастера, обладающие истинным талантом и любовью к своему делу.',
    workImage: '/img/reviews/avatar-2.png',
  },
  {
    id: 'v3',
    type: 'video',
    youtubeId: 'xJPDdCUw6eM',
    videoThumbnail: '/img/video-thumbs/video-3.png',
  },
  {
    id: 't3',
    type: 'text',
    author: 'Ульяна',
    text: 'Мой любимый салон! Очень нравится интерьер и дружелюбный, атмосферный коллектив. Мастера выполняют свою работу на высшем уровне.',
    workImage: '/img/reviews/avatar-3.png',
  },
  {
    id: 'v4',
    type: 'video',
    youtubeId: '-ugTPLnY7k0',
    videoThumbnail: '/img/video-thumbs/video-4.webp',
  },
];

export const stats = [
  { value: '2', label: 'салона' },
  { value: '2014', label: 'работаем более 11 лет' },
  { value: '>30', label: 'специалистов' },
  { value: '6', label: 'направлений' },
  { value: '5.0', label: 'рейтинг' },
];

// src/data/home.ts

export const advantages = [
  {
    title: 'Собственная технология тестирования продуктов',
    description: 'Выбраковывает до 80% образцов, оставляя только лучшие решения для клиентов',
    icon: '/img/advantages/cosmetics_creme.svg',
  },
  {
    title: 'Эксперты международного класса',
    description: 'Команда, которая не просто следует стандартам индустрии, а формирует их',
    icon: '/img/advantages/star_hand_quality_guarantee.svg',
  },
  {
    title: 'Гарантия на работы',
    description: 'Отвечаем за качество каждой процедуры',
    icon: '/img/advantages/profession_teacher.svg',
  },
  {
    title: 'Технологии комфорта',
    description: 'В наших салонах можно расслабиться, перестать контролировать и довериться профессионалам',
    icon: '/img/advantages/armchair_comfort.svg',
  },
  {
    title: 'Work Lounge',
    description: 'В каждом салоне оборудована зона, где можно комфортно разместиться с ноутбуком и выпить кофе',
    icon: '/img/advantages/armchair_comfort.svg',
  },
  {
    title: '3D-подход к красоте',
    description: 'Мы предлагаем только те процедуры, которые гарантированно сохранят и усилят здоровье ваших волос',
    icon: '/img/advantages/guarantee_check.svg',
  },
];

