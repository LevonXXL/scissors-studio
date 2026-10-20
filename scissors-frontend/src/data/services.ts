// src/data/services.ts
import type { SalonSlug } from 'src/data/salons';

export interface SalonPrices {
  universal: string;
  topStylist: string;
  artDirector: string;
}

export interface ServiceItem {
  name: string;
  description: string;
  duration: string;
  availableIn: SalonSlug[];
  prices: {
    moscow?: SalonPrices;
    zelenograd?: SalonPrices;
  };
}

export interface ServiceCategory {
  slug: string;
  title: string;
  sectionTitle: string;
  intro: string;
  availableIn: SalonSlug[];
  items: ServiceItem[];
}

export const serviceCategories: ServiceCategory[] = [
  {
    slug: 'hair',
    title: 'Для волос',
    sectionTitle: 'Парикмахерские услуги и уход',
    intro: 'Услуги для волос от мастеров-парикмахеров. Стоимость услуг состоит из сервисного обслуживания и услуги мастера.',
    availableIn: ['moscow', 'zelenograd'],
    items: [
      {
        name: 'Женская стрижка + Полировка волос',
        description: 'Стрижка с учётом структуры волос и формы лица, полировка для удаления секущихся кончиков',
        duration: '90 минут',
        availableIn: ['moscow', 'zelenograd'],
        prices: {
          moscow: { universal: '5500 | 6500', topStylist: '7500 | 8500', artDirector: '11000' },
          zelenograd: { universal: '4000 | 4500', topStylist: '5500 | 6500', artDirector: '8500' },
        },
      },
      {
        name: 'Сложное окрашивание и плавные переходы',
        description: 'Airtouch, Balayage, Shatush и другие современные техники окрашивания',
        duration: '180+ минут',
        availableIn: ['moscow', 'zelenograd'],
        prices: {
          moscow: {
            universal: 'Короткие\n9000 | 10000\n\nСредние\n10000 | 11000\n\nДлинные\n12000 | 13000',
            topStylist: 'Короткие\n11000 | 13000\n\nСредние\n12000 | 14500\n\nДлинные\n14500 | 16000',
            artDirector: 'Короткие\n13000\n\nСредние\n15000\n\nДлинные\n18000'
          },
          zelenograd: {
            universal: 'Короткие\n8000 | 9000\n\nСредние\n9000 | 10000\n\nДлинные\n11000 | 12000',
            topStylist: 'Короткие\n10000 | 12000\n\nСредние\n11000 | 13000\n\nДлинные\n13000 | 15000',
            artDirector: 'Короткие\n12000\n\nСредние\n14000\n\nДлинные\n17000'
          },
        },
      },
      {
        name: 'Окрашивание с акцентами',
        description: 'Окрашивание с акцентными прядями для создания объема и глубины цвета',
        duration: '150 минут',
        availableIn: ['moscow', 'zelenograd'],
        prices: {
          moscow: { universal: '7000 | 8000', topStylist: '9000 | 10000', artDirector: '12000' },
          zelenograd: { universal: '6000 | 7000', topStylist: '8000 | 9000', artDirector: '11000' },
        },
      },
      {
        name: 'Глянцевое окрашивание',
        description: 'Окрашивание с эффектом глянцевого блеска и насыщенного цвета',
        duration: '120 минут',
        availableIn: ['moscow', 'zelenograd'],
        prices: {
          moscow: { universal: '6000 | 7000', topStylist: '8000 | 9000', artDirector: '11000' },
          zelenograd: { universal: '5000 | 6000', topStylist: '7000 | 8000', artDirector: '10000' },
        },
      },
      {
        name: 'Бережное тонирование',
        description: 'Деликатное тонирование для освежения цвета без агрессивного воздействия',
        duration: '90 минут',
        availableIn: ['moscow', 'zelenograd'],
        prices: {
          moscow: { universal: '4000 | 4500', topStylist: '5500 | 6500', artDirector: '8000' },
          zelenograd: { universal: '3500 | 4000', topStylist: '5000 | 6000', artDirector: '7500' },
        },
      },
      {
        name: 'Бережная смывка. 1-2 тона',
        description: 'Деликатное осветление на 1-2 тона без повреждения структуры волос',
        duration: '120 минут',
        availableIn: ['moscow', 'zelenograd'],
        prices: {
          moscow: { universal: '5000 | 6000', topStylist: '7000 | 8000', artDirector: '10000' },
          zelenograd: { universal: '4500 | 5500', topStylist: '6500 | 7500', artDirector: '9500' },
        },
      },
      {
        name: 'Экспресс коррекция Желтого',
        description: 'Быстрая коррекция нежелательного желтого оттенка',
        duration: '60 минут',
        availableIn: ['moscow', 'zelenograd'],
        prices: {
          moscow: { universal: '3500 | 4000', topStylist: '5000 | 5500', artDirector: '7000' },
          zelenograd: { universal: '3000 | 3500', topStylist: '4500 | 5000', artDirector: '6500' },
        },
      },
      {
        name: 'Репигментация "Выход из блонда"',
        description: 'Возвращение к натуральному или более темному цвету из блонда',
        duration: '150 минут',
        availableIn: ['moscow', 'zelenograd'],
        prices: {
          moscow: { universal: '8000 | 9000', topStylist: '11000 | 13000', artDirector: '15000' },
          zelenograd: { universal: '7000 | 8000', topStylist: '10000 | 12000', artDirector: '14000' },
        },
      },
      {
        name: 'Повторный блонд',
        description: 'Осветление отросших корней для поддержания блонда',
        duration: '120 минут',
        availableIn: ['moscow', 'zelenograd'],
        prices: {
          moscow: { universal: '6000 | 7000', topStylist: '8000 | 9000', artDirector: '12000' },
          zelenograd: { universal: '5500 | 6500', topStylist: '7500 | 8500', artDirector: '11000' },
        },
      },
      {
        name: 'Первичный блонд',
        description: 'Полное осветление до состояния блонда',
        duration: '180+ минут',
        availableIn: ['zelenograd'], // Есть только в Зеленограде согласно HTML
        prices: {
          moscow: { universal: 'Уточняйте', topStylist: 'Уточняйте', artDirector: 'Уточняйте' },
          zelenograd: { universal: '9000 | 10000', topStylist: '12000 | 14000', artDirector: '16000' },
        },
      },
      {
        name: 'Air Touch',
        description: 'Современная техника окрашивания с воздушным, естественным переходом цвета',
        duration: '180+ минут',
        availableIn: ['zelenograd'], // Есть только в Зеленограде согласно HTML
        prices: {
          moscow: { universal: 'Уточняйте', topStylist: 'Уточняйте', artDirector: 'Уточняйте' },
          zelenograd: { universal: '9500 | 11000', topStylist: '12500 | 15000', artDirector: '17000' },
        },
      },
      {
        name: 'Стойкая завивка',
        description: 'Четко выраженный локон и объем, стойкость до 5-6 месяцев. В процедуру входит коллагеновый уход.',
        duration: '180-270 минут',
        availableIn: ['moscow', 'zelenograd'],
        prices: {
          moscow: { universal: 'Любая длина\n3500 | 4000', topStylist: 'Любая длина\n4000 | 4500', artDirector: 'Любая длина\n6000' },
          zelenograd: { universal: 'Любая длина\n3000 | 3500', topStylist: 'Любая длина\n3500 | 4000', artDirector: 'Любая длина\n5500' },
        },
      },
      {
        name: 'Лиссинг - Долговременное выпрямление',
        description: 'Долговременное выпрямление волос с эффектом гладкости и блеска',
        duration: '180 минут',
        availableIn: ['moscow', 'zelenograd'],
        prices: {
          moscow: {
            universal: 'Короткие\n8000 | 9000\n\nСредние\n10000 | 12000\n\nДлинные\n12000 | 14000',
            topStylist: 'Короткие\n10000 | 12000\n\nСредние\n12000 | 14000\n\nДлинные\n14000 | 16000',
            artDirector: 'Короткие\n14000\n\nСредние\n16000\n\nДлинные\n18000'
          },
          zelenograd: {
            universal: 'Короткие\n7500 | 8500\n\nСредние\n9500 | 11000\n\nДлинные\n11000 | 13000',
            topStylist: 'Короткие\n9500 | 11000\n\nСредние\n11000 | 13000\n\nДлинные\n13000 | 15000',
            artDirector: 'Короткие\n13000\n\nСредние\n15000\n\nДлинные\n17000'
          },
        },
      },
      {
        name: 'Молекулярная био-реконструкция волос',
        description: 'Молекулярное восстановление сильно поврежденных волос. Рекомендуется курсом из 5-10 процедур.',
        duration: '60 минут',
        availableIn: ['moscow', 'zelenograd'],
        prices: {
          moscow: { universal: '5000 | 5500', topStylist: '7500 | 8500', artDirector: '11000' },
          zelenograd: { universal: '4500 | 5000', topStylist: '7000 | 8000', artDirector: '10000' },
        },
      },
      {
        name: 'Авторский уход SCISSORS',
        description: 'Интенсивное увлажнение и восстановление упругости, эластичности и блеска волос без формальдегидов.',
        duration: '60 минут',
        availableIn: ['moscow', 'zelenograd'],
        prices: {
          moscow: { universal: '4500 | 5000', topStylist: '6500 | 7500', artDirector: '9000' },
          zelenograd: { universal: '4000 | 4500', topStylist: '6000 | 7000', artDirector: '8500' },
        },
      },
      {
        name: 'Экстраблеск',
        description: 'Процедура для придания волосам максимального блеска и сияния',
        duration: '60 минут',
        availableIn: ['moscow', 'zelenograd'],
        prices: {
          moscow: { universal: '4000 | 4500', topStylist: '6000 | 7000', artDirector: '8500' },
          zelenograd: { universal: '3500 | 4000', topStylist: '5500 | 6500', artDirector: '8000' },
        },
      },
      {
        name: 'Эко детокс',
        description: 'Глубокое очищение волос и кожи головы от накопленных загрязнений и остатков укладочных средств',
        duration: '60 минут',
        availableIn: ['moscow', 'zelenograd'],
        prices: {
          moscow: { universal: '3500 | 4000', topStylist: '5000 | 6000', artDirector: '7500' },
          zelenograd: { universal: '3000 | 3500', topStylist: '4500 | 5500', artDirector: '7000' },
        },
      },
      {
        name: 'Холодный ботокс',
        description: 'Интенсивное восстановление и питание волос без нагревания',
        duration: '60 минут',
        availableIn: ['moscow', 'zelenograd'],
        prices: {
          moscow: { universal: '4500 | 5000', topStylist: '6500 | 7500', artDirector: '9000' },
          zelenograd: { universal: '4000 | 4500', topStylist: '6000 | 7000', artDirector: '8500' },
        },
      },
      {
        name: 'Ламинирование волос с SPF',
        description: 'Защитное покрытие для волос с УФ-фильтрами, придающее блеск и гладкость',
        duration: '60 минут',
        availableIn: ['moscow', 'zelenograd'],
        prices: {
          moscow: { universal: '4000 | 4500', topStylist: '6000 | 7000', artDirector: '8500' },
          zelenograd: { universal: '3500 | 4000', topStylist: '5500 | 6500', artDirector: '8000' },
        },
      },
      {
        name: 'Экспресс уходы для волос',
        description: 'Быстрые процедуры для мгновенного улучшения состояния волос',
        duration: '30 минут',
        availableIn: ['zelenograd'], // Есть только в Зеленограде согласно HTML
        prices: {
          moscow: { universal: 'Уточняйте', topStylist: 'Уточняйте', artDirector: 'Уточняйте' },
          zelenograd: { universal: '2500 | 3000', topStylist: '3500 | 4000', artDirector: '5000' },
        },
      },
    ],
  },
  {
    slug: 'nails',
    title: 'Для ногтей',
    sectionTitle: 'Маникюр, педикюр и дизайн',
    intro: 'Услуги для ногтей от мастеров. Стоимость услуг состоит из сервисного обслуживания и услуги мастера.',
    // Если маникюр в Москве не предоставляется вообще, можно убрать 'moscow' отсюда,
    // либо оставить, но ниже указать, что услуги нет. Пока оставим оба салона для категории,
    // но конкретные услуги привяжем к Зеленограду, как в твоем дампе.
    availableIn: ['zelenograd'],
    items: [
      {
        name: 'Маникюр',
        description: 'Женский / мужской маникюр - Комбинированный или обрезной (по запросу). Детский маникюр - бережный необрезной (для детей 10-14 лет).',
        duration: '45 / 60 / 30 минут',
        availableIn: ['zelenograd'], // Только Зеленоград, согласно дампу
        prices: {
          zelenograd: {
            universal: 'Уточняйте',
            topStylist: 'Женский: 1400\nДетский: 1000',
            artDirector: 'Уточняйте'
          }
        },
      },
      {
        name: 'Комплекс: Маникюр + покрытие лаком или PLEX',
        description: 'Комплекс "Покрытие лаком + маникюр все включено" или Маникюр + лечебное покрытие PLEX.',
        duration: '60 минут',
        availableIn: ['zelenograd'],
        prices: {
          zelenograd: {
            universal: 'Уточняйте',
            topStylist: 'PLEX: 2000\nМаникюр + покрытие лаком: 2350',
            artDirector: 'Уточняйте'
          }
        },
      },
      {
        name: 'Дизайн ногтей',
        description: 'Простой дизайн всех ногтей (втирка, стемпинг, наклейки, стразы, слайдеры). Простой дизайн 1 ногтя. Роспись. Инкрустация. Градиент.',
        duration: '5-30 минут',
        availableIn: ['zelenograd'],
        prices: {
          zelenograd: {
            universal: 'Уточняйте',
            topStylist: 'Простой дизайн всех ногтей: 1200\nПростой дизайн 1 ногтя: 130 | 180\nРоспись | Инкрустация: 750 | 780\nГрадиент: 1300',
            artDirector: 'Уточняйте'
          }
        },
      },
      {
        name: 'Педикюр',
        description: 'Женский педикюр, SMART педикюр, пилочный педикюр, экспресс педикюр.',
        duration: '60-90 минут',
        availableIn: ['zelenograd'],
        prices: {
          zelenograd: {
            universal: 'Уточняйте',
            topStylist: 'Женский педикюр: 2900\nSMART педикюр: 3250\nПилочный педикюр: 3500\nЭкспресс педикюр: 2100',
            artDirector: 'Уточняйте'
          }
        },
      },
      {
        name: 'Педикюр "Все включено"',
        description: 'Педикюр с покрытием гель-лак. Обработка всей стопы и пальцев (со снятием или без), либо экспресс-вариант (только пальцы).',
        duration: '60 минут',
        availableIn: ['zelenograd'],
        prices: {
          zelenograd: {
            universal: 'Уточняйте',
            topStylist: 'Со снятием | без снятия: 4200 | 3950\nЭкспресс педикюр все включено: 3350',
            artDirector: 'Уточняйте'
          }
        },
      },
      {
        name: 'Покрытие и снятие',
        description: 'Покрытие лаком (в дополнение к маникюру/педикюру). Снятие лака или гель-лака. Снятие искусственных ногтей.',
        duration: '10-30 минут',
        availableIn: ['zelenograd'],
        prices: {
          zelenograd: {
            universal: 'Уточняйте',
            topStylist: 'Покрытие лак: 700\nСнятие лак | гель-лак: 250 | 550\nСнятие искусственных ногтей: 1400',
            artDirector: 'Уточняйте'
          }
        },
      },
      {
        name: 'Ремонт и укрепление',
        description: 'Наращивание 1 ногтя. Ремонт и укрепление 1 ногтя гелем или акрилом.',
        duration: '10-15 минут',
        availableIn: ['zelenograd'],
        prices: {
          zelenograd: {
            universal: 'Уточняйте',
            topStylist: 'Наращивание 1 ногтя: 450\nРемонт и укрепление 1 ногтя Гель | акрил: 350 | 350',
            artDirector: 'Уточняйте'
          }
        },
      },
      {
        name: 'Подология',
        description: 'Тампонада околоногтевых валиков (1 ноготь). Обработка трещин. Постановка разгрузки на трещину. Зачистка онихолизиса (1 ноготь).',
        duration: '10-20 минут',
        availableIn: ['zelenograd'],
        prices: {
          zelenograd: {
            universal: 'Уточняйте',
            topStylist: 'Тампонада: 400\nОбработка трещин: 750\nПостановка разгрузки: 400\nЗачистка онихолизиса: 400',
            artDirector: 'Уточняйте'
          }
        },
      },
      {
        name: 'Питание и уход',
        description: 'Лечебный лак, лечебное покрытие PLEX, уход Soft touch, СПА перчатки, СПА Релакс.',
        duration: '15-30 минут',
        availableIn: ['zelenograd'],
        prices: {
          zelenograd: {
            universal: 'Уточняйте',
            topStylist: 'Лечебный лак | PLEX покрытие: 600 | 1100\nУход Soft touch: 600\nСПА перчатки: 1200\nСПА Релакс: 1500',
            artDirector: 'Уточняйте'
          }
        },
      },
      {
        name: 'Комплексы: Наращивание',
        description: 'Наращивание ногтей с дизайном (до 7 мм, свыше 7 мм, экстрадлинные).',
        duration: '120-180 минут',
        availableIn: ['zelenograd'],
        prices: {
          zelenograd: {
            universal: 'Уточняйте',
            topStylist: 'Наращивание до 7 мм: 5300\nНаращивание свыше 7 мм: 6200\nЭкстрадлинные: 8400',
            artDirector: 'Уточняйте'
          }
        },
      },
    ],
  },
  {
    slug: 'cosmetology',
    title: 'Косметология',
    sectionTitle: 'Уход за лицом',
    intro: 'Услуги от мастеров-косметологов. Стоимость услуг состоит из сервисного обслуживания и услуги мастера.',
    availableIn: ['moscow', 'zelenograd'],
    items: [
      {
        name: 'УЗ-чистка',
        description: 'Аппаратное очищение при помощи ультразвуковых волн высокой частоты',
        duration: '60 минут',
        availableIn: ['moscow', 'zelenograd'],
        prices: {
          moscow: { universal: '2500', topStylist: '3500', artDirector: '4500' },
          zelenograd: { universal: '2300', topStylist: '3300', artDirector: '4300' },
        },
      },
    ],
  },
  {
    slug: 'browlashes',
    title: 'Брови и ресницы',
    sectionTitle: 'Брови',
    intro: 'Услуги для бровей от мастеров-стилистов. Стоимость услуг состоит из сервисного обслуживания и услуги мастера.',
    availableIn: ['moscow', 'zelenograd'],
    items: [
      {
        name: 'Архитектура бровей',
        description: 'Построение формы бровей и окрашивание краской или хной',
        duration: '30 минут',
        availableIn: ['moscow', 'zelenograd'],
        prices: {
          moscow: { universal: '1300–1900', topStylist: '2400', artDirector: '3500' },
          zelenograd: { universal: '1200–1800', topStylist: '2300', artDirector: '3300' },
        },
      },
    ],
  },
  {
    slug: 'epilation',
    title: 'Эпиляция',
    sectionTitle: 'Лазерная эпиляция',
    intro: 'Услуги от мастеров. Стоимость услуг состоит из сервисного обслуживания и услуги мастера.',
    availableIn: ['moscow', 'zelenograd'],
    items: [],
  },
  {
    slug: 'forman',
    title: 'Для мужчин',
    sectionTitle: 'Мужские стрижки и уход',
    intro: 'Услуги для мужчин от мастеров. Стоимость услуг состоит из сервисного обслуживания и услуги мастера.',
    availableIn: ['moscow', 'zelenograd'],
    items: [],
  },
];
