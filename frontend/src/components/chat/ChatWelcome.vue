<template>
  <div class="chat-welcome">
    <div class="cw-box">
      <h1>{{ t('welcome.title') }}</h1>
      <p>{{ t('welcome.subtitle') }}</p>
    </div>
    <div class="cw-grid">
      <button
        v-for="topic in topics"
        :key="topic"
        class="cw-card"
        @click="$emit('select', topic)"
      >
        <div class="cw-card-t">{{ topic }}</div>
        <div class="cw-card-d">{{ t('welcome.cardDesc') }}</div>
      </button>
    </div>
  </div>
</template>

<script setup>
import { useI18n } from '@/features/chat/i18n'

defineProps({
  topics: { type: Array, default: () => [] }
})
defineEmits(['select'])
const { t } = useI18n()
</script>

<style lang="scss" scoped>
.chat-welcome {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
   padding: calc(32px * var(--chat-space-scale)) 20px calc(40px * var(--chat-space-scale));
   max-width: var(--chat-content-width);
  width: 100%;
  margin: 0 auto;
}
.cw-box { text-align: center; margin-bottom: 32px; }
.cw-box h1 { font-size: 24px; font-weight: 600; line-height: 1.33; margin-bottom: 10px; color: var(--chat-ink); }
.cw-box p { font-size: 15px; color: var(--chat-hollow); }
.cw-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.cw-card {
  background: var(--chat-canvas);
  border: 1px solid var(--chat-hairline);
  border-radius: var(--chat-radius);
  padding: 14px;
  cursor: pointer;
  text-align: left;
  font-family: inherit;
  transition: background .15s;
  &:hover { background: var(--chat-hover); border-color: var(--chat-accent-border); }
  .cw-card-t { font-size: 14px; font-weight: 500; margin-bottom: 4px; color: var(--chat-ink); }
  .cw-card-d { font-size: 13px; color: var(--chat-hollow); line-height: 1.45; }
}
</style>
