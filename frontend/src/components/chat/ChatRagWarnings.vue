<template>
  <div v-if="items.length" class="chat-rag-warnings" role="alert">
    <div class="crw-title">
      <svg viewBox="0 0 24 24" fill="none" stroke-width="1.8">
        <path d="M12 3l7 3v5c0 4.5-3 8-7 10-4-2-7-5.5-7-10V6l7-3z" />
        <path d="M12 8v4M12 15.5h.01" />
      </svg>
      <span>已拦截 {{ items.length }} 条可疑知识引用</span>
    </div>
    <ul class="crw-list">
      <li v-for="item in items" :key="item.id + item.flagsText" class="crw-item">
        <code>{{ item.id }}</code>
        <span v-if="item.flagsText">{{ item.flagsText }}</span>
        <span v-else>检测到注入特征</span>
      </li>
    </ul>
    <p class="crw-note">以上内容未进入模型上下文，回答未受其影响。</p>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { parseRagWarning } from '@/features/security/warningCodes'

const props = defineProps({
  warnings: { type: Array, default: () => [] }
})

const items = computed(() => (props.warnings || []).map(parseRagWarning))
</script>

<style lang="scss" scoped>
.chat-rag-warnings {
  margin-top: 14px;
  padding: 12px 14px;
  border: 1px solid #f5cba0;
  border-radius: var(--chat-radius);
  background: #fdf3e4;
}
.crw-title {
  display: flex; align-items: center; gap: 8px;
  color: #8a4b08; font-size: 13px; font-weight: 600;
  svg { width: 16px; height: 16px; stroke: #c07b1f; flex-shrink: 0; }
}
.crw-list {
  margin: 8px 0 0; padding: 0; list-style: none;
}
.crw-item {
  display: flex; gap: 8px; flex-wrap: wrap; align-items: baseline;
  font-size: 12.5px; color: #7c5d14; line-height: 1.6;
  code { color: #8a4b08; font-weight: 600; }
}
.crw-note {
  margin: 8px 0 0; font-size: 12px; color: #a4762a;
}
</style>
