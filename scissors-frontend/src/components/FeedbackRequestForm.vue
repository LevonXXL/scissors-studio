<template>
  <div v-if="submitted" class="text-center q-py-xl" role="status">
    <q-icon name="check_circle" size="52px" color="positive" />
    <p class="text-body1 q-mt-md q-mb-none">Обращение сохранено. Мы свяжемся с вами.</p>
  </div>
  <form v-else class="feedback-request-form" @submit.prevent="submit">
    <div class="q-gutter-md">
      <q-input v-model.trim="name" outlined label="Как к вам обращаться" autocomplete="name" maxlength="100" />
      <q-input v-model.trim="contact" outlined label="Телефон или email" maxlength="254" />
      <q-input v-model.trim="message" outlined autogrow type="textarea" label="Ваш вопрос" maxlength="4000" />
      <q-checkbox v-model="consent" dense>
        <span class="text-caption">Я соглашаюсь с <router-link to="/privacy" @click="emit('privacy')">политикой обработки персональных данных</router-link></span>
      </q-checkbox>
    </div>
    <q-banner v-if="error" class="bg-red-1 text-negative q-mt-md" rounded>{{ error }}</q-banner>
    <q-btn type="submit" unelevated no-caps color="primary" label="Отправить" class="q-mt-lg"
      :loading="busy" :disable="!canSubmit" />
  </form>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { ApiError } from '@/api/client';
import { createFeedbackRequest } from '@/api/endpoints';
import type { FeedbackDraft } from '@/data/feedbackMessenger';

const props = defineProps<{ initialDraft?: FeedbackDraft }>();
const emit = defineEmits<{ draft: [value: FeedbackDraft]; privacy: [] }>();
const name = ref(props.initialDraft?.name ?? '');
const contact = ref(props.initialDraft?.phone ?? '');
const message = ref(props.initialDraft?.message ?? '');
const consent = ref(false);
const busy = ref(false);
const submitted = ref(false);
const error = ref('');
const canSubmit = computed(() => name.value.trim().length >= 2 && contact.value.trim() !== '' && message.value.trim().length >= 2 && consent.value);

watch([name, contact, message], () => {
  emit('draft', { name: name.value, phone: contact.value, message: message.value });
});

async function submit() {
  if (!canSubmit.value || busy.value) return;
  busy.value = true;
  error.value = '';
  try {
    await createFeedbackRequest({ name: name.value, phone: contact.value, message: message.value });
    submitted.value = true;
  } catch (cause) {
    error.value = cause instanceof ApiError ? cause.message : 'Не удалось сохранить обращение. Попробуйте ещё раз.';
  } finally {
    busy.value = false;
  }
}
</script>
