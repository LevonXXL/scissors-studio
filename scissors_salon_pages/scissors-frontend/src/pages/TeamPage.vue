<template>
  <q-page class="q-px-md q-py-xl" style="max-width: 1200px; margin: 0 auto">

    <!-- Хлебные крошки -->
    <div class="text-caption text-grey-7 q-mb-md">
      <router-link to="/" class="text-primary" style="text-decoration: none;">Главная</router-link>
      <span class="q-mx-xs">/</span>
      <span class="text-grey-9">Команда и портфолио</span>
    </div>

    <h1 class="text-h4 text-weight-bold q-mb-lg">Команда и портфолио</h1>

    <!-- Описание категорий мастеров -->
    <q-card flat bordered class="q-mb-xl q-pa-md bg-grey-1">
      <div class="text-subtitle1 text-weight-bold q-mb-sm">Как выбрать категорию мастера?</div>
      <p class="text-body2 text-grey-8 q-mb-sm">
        Категория мастера отражает его опыт, уровень самостоятельности и глубину работы с образом.
        Рост категории определяется временем работы в Scissors, регулярным обучением,
        подтверждённой квалификацией и вкладом в развитие команды.
      </p>
      <p class="text-body2 text-grey-8">
        Все мастера работают на высоком профессиональном уровне. Разница — в скорости,
        опыте и умении выстраивать долгосрочную стратегию работы с клиентом.
      </p>
    </q-card>

    <!-- Фильтр по салонам -->
    <div v-if="teamStore.salons.length" class="row q-gutter-sm q-mb-lg">
      <q-btn
          v-for="salon in teamStore.salons"
          :key="salon.id"
          :label="salon.name"
          :color="selectedSalonId === salon.id ? 'primary' : 'grey-3'"
          :text-color="selectedSalonId === salon.id ? 'white' : 'dark'"
          @click="selectedSalonId = salon.id"
          class="no-uppercase"
      />
      <q-btn
          label="Все салоны"
          :color="!selectedSalonId ? 'primary' : 'grey-3'"
          :text-color="!selectedSalonId ? 'white' : 'dark'"
          @click="selectedSalonId = null"
          class="no-uppercase"
      />
    </div>

    <!-- Загрузка -->
    <div v-if="!teamStore.loaded" class="text-center q-pa-xl">
      <q-spinner color="primary" size="3em" />
      <div class="text-body1 text-grey-7 q-mt-md">Загрузка команды...</div>
    </div>

    <!-- Сетка мастеров -->
    <div v-else class="row q-col-gutter-lg">
      <div
          v-for="master in filteredMasters"
          :key="master.id"
          class="col-12 col-sm-6 col-md-4 col-lg-3"
      >
        <q-card flat bordered class="full-height team-card hover-lift">
          <!-- Фото мастера -->
          <q-img
              v-if="master.photo"
              :src="master.photo"
              class="bg-grey-2"
          >
            <template v-slot:loading>
              <div class="flex flex-center">
                <q-spinner color="primary" size="3em" />
              </div>
            </template>
            <template v-slot:error>
              <div class="absolute-full flex flex-center bg-grey-3">
                <q-icon name="person" size="3em" color="grey-5" />
              </div>
            </template>
          </q-img>
          <div v-else class="bg-grey-2 flex flex-center" style="aspect-ratio: 1/1">
            <q-icon name="person" size="4em" color="grey-4" />
          </div>

          <q-card-section>
            <!-- Категория -->
            <div class="text-caption text-weight-bold text-primary q-mb-xs" style="text-transform: uppercase;">
              {{ master.category_display }}
            </div>

            <!-- Имя -->
            <div class="text-h6 text-weight-bold q-mb-sm">
              {{ master.name }}
            </div>

            <!-- Специализация -->
            <div v-if="master.specialization" class="text-body2 text-grey-7 q-mb-xs">
              {{ master.specialization }}
            </div>

            <!-- Описание -->
            <div class="text-body2 text-grey-8" style="line-height: 1.5;" v-html="master.bio"/>

            <!-- Салоны, где работает мастер -->
            <div class="q-mt-sm">
              <q-badge
                  v-for="salon in master.salon_details"
                  :key="salon.id"
                  color="grey-3"
                  text-color="dark"
                  class="q-mr-xs"
              >
                {{ salon.name }}
              </q-badge>
            </div>
          </q-card-section>

          <q-card-actions align="center" class="q-pb-md">
            <q-btn
                flat
                no-caps
                label="Подробнее и портфолио"
                color="primary"
                :to="`/team/${master.slug}`"
            />
          </q-card-actions>
        </q-card>
      </div>
    </div>

    <!-- Сообщение, если мастеров нет -->
    <div v-if="teamStore.loaded && !filteredMasters.length" class="text-center q-pa-xl">
      <q-icon name="person" size="4em" color="grey-5" />
      <div class="text-h6 text-grey-7 q-mt-md">В этом салоне пока нет мастеров</div>
    </div>

    <!-- CTA: Стать частью команды -->
    <div class="text-center q-mt-xl q-pa-xl bg-primary text-white rounded-borders">
      <div class="text-h6 text-weight-bold q-mb-sm">Хочу в команду</div>
      <p class="text-body2 q-mb-md">Оставьте заявку, ваш бьюти-ассистент свяжется с вами</p>
      <q-btn
          unelevated
          no-caps
          label="Стать частью команды"
          color="white"
          text-color="primary"
          @click="openVacancyForm"
      />
    </div>

  </q-page>
</template>

<script setup lang="ts">
import { ref, computed, onServerPrefetch } from 'vue';
import { useMeta } from 'quasar';
import { useTeamStore } from '@/stores/team';

const teamStore = useTeamStore();

// Запускаем загрузку один раз сразу (работает и на сервере, и на клиенте).
// onServerPrefetch просто дожидается этого же промиса на сервере — без
// повторного запроса. Состояние Pinia-стора сериализуется Quasar SSR и
// переиспользуется на клиенте один в один, поэтому hydration mismatch нет.
const initialLoad = teamStore.load();
onServerPrefetch(() => initialLoad);

// UI-состояние фильтра — только клиентское, не нужно в Pinia
const selectedSalonId = ref<number | null>(null);

const filteredMasters = computed(() => {
  if (!selectedSalonId.value) {
    return teamStore.masters;
  }
  return teamStore.masters.filter(m =>
      m.salon_details.some(s => s.id === selectedSalonId.value),
  );
});

useMeta({
  title: 'Команда и портфолио — Scissors Studio',
  meta: {
    description: {
      name: 'description',
      content: 'Познакомьтесь с командой мастеров Scissors Studio. Опытные специалисты, тренеры и арт-директора с международным опытом.',
    }
  }
});

const openVacancyForm = () => {
  // TODO: Открыть форму заявки на вакансию
  console.log('Открыть форму "Хочу в команду"');
};
</script>

<style scoped>
.team-card {
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.hover-lift:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 16px rgba(0,0,0,0.1) !important;
}

.rounded-borders {
  border-radius: 12px;
}
</style>
