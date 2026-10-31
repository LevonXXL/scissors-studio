<template>
  <q-dialog :model-value="modelValue" @update:model-value="emit('update:modelValue', $event)">
    <q-card class="feedback-dialog full-width">
      <q-card-section class="row items-start justify-between q-pb-sm">
        <div>
          <div class="text-h5 text-weight-bold">Обратная связь</div>
          <p class="text-body2 text-grey-7 q-mt-xs q-mb-none">Выберите удобный способ связи.</p>
        </div>
        <q-btn flat round dense icon="close" aria-label="Закрыть" v-close-popup />
      </q-card-section>

      <q-card-section class="q-pt-sm">
        <div class="row q-col-gutter-sm q-mb-lg">
          <div class="col-12 col-sm-6">
            <q-btn class="full-width" no-caps :outline="method !== 'call'" :unelevated="method === 'call'" color="primary" icon="phone_callback" label="Связаться со мной" @click="method = 'call'; error = ''" />
          </div>
          <div class="col-12 col-sm-6">
            <q-btn class="full-width" no-caps :outline="method !== 'message'" :unelevated="method === 'message'" color="primary" icon="chat" label="Написать" @click="method = 'message'; error = ''" />
          </div>
        </div>

        <FeedbackRequestForm v-if="method === 'call' && modelValue" :initial-draft="draft"
          @draft="updateDraft" @privacy="emit('update:modelValue', false)" />
        <template v-else>
          <q-input v-model="message" outlined autogrow type="textarea" label="Текст сообщения" maxlength="4000" />
          <p class="text-caption text-grey-7 q-mt-md q-mb-sm">Кнопка MAX открывает чат поддержки и копирует текст для вставки вручную. Если браузер запретит копирование, воспользуйтесь кнопкой «Скопировать текст».</p>
          <div class="row q-gutter-sm">
            <q-btn v-for="link in messengerLinks" :key="link.label" outline no-caps color="primary" :icon="link.icon" :label="link.label" :href="primaryMessengerHref(link, currentDraft(), siteUrl())" target="_blank" rel="noopener noreferrer" @click="onMessengerClick(link)" />
            <q-btn flat no-caps icon="content_copy" label="Скопировать текст" :disable="!formattedMessage" @click="copyMessage" />
          </div>
          <div v-if="formattedMessage" class="row q-gutter-sm q-mt-sm">
            <q-btn flat no-caps color="primary" label="Выбрать чат в Telegram" :href="telegramShareHref(formattedMessage, siteUrl())" target="_blank" rel="noopener noreferrer" />
            <q-btn flat no-caps color="primary" label="Поделиться через MAX — выбрать чат" :href="messengerHref(maxSupportLink, currentDraft(), siteUrl())" target="_blank" rel="noopener noreferrer" />
          </div>
        </template>
        <q-banner v-if="method === 'message' && error" class="bg-red-1 text-negative q-mt-md" rounded>{{ error }}</q-banner>
        <q-banner v-if="method === 'message' && copied" class="bg-blue-1 q-mt-md" rounded>Текст скопирован.</q-banner>
      </q-card-section>

      <q-card-actions align="right" class="q-pa-md">
        <q-btn flat no-caps label="Закрыть" v-close-popup />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import FeedbackRequestForm from '@/components/FeedbackRequestForm.vue';
import { messengerLinks, type MessengerLink } from '@/data/contacts';
import { formatFeedbackMessage, messengerHref, primaryMessengerHref, telegramShareHref, type FeedbackDraft } from '@/data/feedbackMessenger';
import { SITE_URL } from '@/config/urls';

const props = defineProps<{ modelValue: boolean }>();
const emit = defineEmits<{ 'update:modelValue': [value: boolean] }>();

const method = ref<'call' | 'message'>('call');
const draft = ref<FeedbackDraft>({ name: '', phone: '', message: '' });
const message = ref('');
const copied = ref(false);
const error = ref('');
const formattedMessage = computed(() => formatFeedbackMessage(currentDraft()));
const maxSupportLink = messengerLinks.find((link) => link.label === 'MAX')!;

function currentDraft(): FeedbackDraft {
  return { ...draft.value, message: message.value };
}

function updateDraft(value: FeedbackDraft) {
  draft.value = value;
  message.value = value.message;
}

function siteUrl(): string {
  return `${SITE_URL}/`;
}

watch(() => props.modelValue, (open) => {
  if (!open) return;
  method.value = 'call';
  draft.value = { name: '', phone: '', message: '' };
  message.value = '';
  copied.value = false;
  error.value = '';
});

async function copyMessage() {
  try {
    await navigator.clipboard.writeText(formattedMessage.value);
    copied.value = true;
  } catch {
    error.value = 'Не удалось скопировать текст. Скопируйте его вручную.';
  }
}

function onMessengerClick(link: MessengerLink) {
  if (link.label === 'MAX' && formattedMessage.value) void copyMessage();
}
</script>

<style scoped>
.feedback-dialog { max-width: 620px; border-radius: 18px; }
</style>
