<template>
  <q-dialog :model-value="modelValue" @update:model-value="$emit('update:modelValue', $event)">
    <q-card style="min-width: 320px; max-width: 420px">
      <q-card-section>
        <div class="text-h6 text-weight-bold">{{ title }}</div>
        <p class="text-body2 text-grey-8 q-mt-xs q-mb-none">{{ subtitle }}</p>
      </q-card-section>

      <template v-if="!submitted">
        <q-card-section class="q-gutter-md">
          <q-input v-model="name" label="Ваше имя" outlined dense />
          <q-input v-model="phone" label="Телефон" outlined dense mask="+7 (###) ###-##-##" />
          <q-select
            v-model="salonSlug"
            :options="salonOptions"
            emit-value
            map-options
            outlined
            dense
            label="Салон (необязательно)"
            clearable
          />
          <q-checkbox v-model="consent" dense>
            <span class="text-caption">
              Я соглашаюсь с
              <router-link to="/policy" @click="modelValueLocal = false">политикой обработки персональных данных</router-link>
            </span>
          </q-checkbox>
        </q-card-section>

        <q-card-actions align="right">
          <q-btn flat no-caps label="Отмена" v-close-popup />
          <q-btn
            unelevated no-caps label="Отправить заявку"
            :disable="!canSubmit"
            :style="{ background: 'var(--sc-accent)', color: '#fff' }"
            @click="submit"
          />
        </q-card-actions>
      </template>

      <template v-else>
        <q-card-section class="text-center q-py-lg">
          <q-icon name="check_circle" size="48px" :style="{ color: 'var(--sc-accent)' }" />
          <p class="text-body1 q-mt-md q-mb-none">
            Заявка отправлена. Ваш бьюти-ассистент свяжется с вами в ближайшее время.
          </p>
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat no-caps label="Закрыть" v-close-popup />
        </q-card-actions>
      </template>
    </q-card>
  </q-dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { salons } from '@/data/salons';

const props = withDefaults(defineProps<{
  modelValue: boolean;
  title?: string;
  subtitle?: string;
  /** Метка контекста заявки — на будущее, когда появится реальная отправка на бэкенд. */
  context?: string;
}>(), {
  title: 'НУЖНА КОНСУЛЬТАЦИЯ?',
  subtitle: 'Оставьте заявку, ваш бьюти-ассистент свяжется с вами',
  context: 'general',
});

const emit = defineEmits<{ 'update:modelValue': [value: boolean] }>();

const name = ref('');
const phone = ref('');
const salonSlug = ref<string | null>(null);
const consent = ref(false);
const submitted = ref(false);

const salonOptions = salons.map((s) => ({ label: s.city, value: s.slug }));

const canSubmit = computed(() => name.value.trim() !== '' && phone.value.trim() !== '' && consent.value);

// Сбрасываем форму каждый раз, когда модалку открывают заново.
watch(
  () => props.modelValue,
  (isOpen) => {
    if (isOpen) {
      name.value = '';
      phone.value = '';
      salonSlug.value = null;
      consent.value = false;
      submitted.value = false;
    }
  },
);

function submit() {
  // TODO: реальная отправка (Django API) появится на этапе 2 — пока форма
  // только подтверждает приём, без сохранения данных. См. context prop —
  // на этапе бэкенда он поедет вместе с заявкой (общая консультация / вакансия / и т.п.).
  submitted.value = true;
}
</script>
