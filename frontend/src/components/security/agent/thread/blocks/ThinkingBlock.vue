<template>
  <div class="thinking-block">
    <div v-if="showMeta" class="tb-meta">
      <span class="tb-tag">THINKING</span>
      <span v-if="live" class="tb-live">思考中…</span>
      <span v-if="sensitiveLevel === 'truncated'" class="tb-trunc">已截断</span>
    </div>
    <div class="tb-content" :class="{ 'tb-content--collapsed': collapsed }">
      <p v-for="(paragraph, index) in paragraphs" :key="index">
        {{ paragraph }}<span v-if="live && index === paragraphs.length - 1" class="tb-cursor" />
      </p>
    </div>
    <button
      v-if="!live && text"
      type="button"
      class="tb-toggle"
      @click="collapsed = !collapsed"
    >
      <svg class="tb-toggle__chevron" viewBox="0 0 24 24" fill="none" stroke-width="2">
        <polyline points="6 9 12 15 18 9" />
      </svg>
      {{ collapsed ? '展开思考' : '收起思考' }}
    </button>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'

const props = defineProps({
  title: { type: String, default: '推理摘要' },
  text: { type: String, default: '' },
  live: { type: Boolean, default: false },
  sensitiveLevel: { type: String, default: 'internal' },
  showMeta: { type: Boolean, default: true }
})

const collapsed = ref(false)

// 实时思考时自动展开；结束后保留用户当前查看状态
watch(
  () => props.live,
  (live) => {
    if (live) collapsed.value = false
  }
)

const paragraphs = computed(() => {
  const text = props.text || ''
  return text
    .split(/\n+/)
    .map((line) => line.trim())
    .filter(Boolean)
})
</script>

<style scoped lang="scss">
.thinking-block {
  padding: 2px 0 14px;
  animation: tb-fade 0.3s ease;
}

@keyframes tb-fade {
  from {
    opacity: 0;
    transform: translateY(4px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.tb-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  color: var(--chat-hollow);
  margin-bottom: 6px;
}

.tb-tag {
  padding: 1px 6px;
  border-radius: 4px;
  font-weight: 600;
  font-size: 10px;
  letter-spacing: 0.04em;
  background: rgba(124, 58, 237, 0.1);
  color: #7c3aed;
}

.tb-live {
  color: var(--chat-accent);
  animation: tb-pulse 1.4s infinite ease-in-out;
}

.tb-trunc {
  font-size: 10px;
  color: var(--chat-warning-ink);
  background: var(--chat-warning-bg);
  border-radius: 999px;
  padding: 1px 8px;
}

.tb-content p {
  margin-bottom: 10px;
  color: var(--chat-ink);
  font-size: calc(14.5px * var(--chat-font-scale));
  line-height: 1.75;
  white-space: pre-wrap;
  word-break: break-word;
}

.tb-content p:last-child {
  margin-bottom: 0;
}

.tb-content--collapsed {
  display: none;
}

.tb-toggle {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  border: 0;
  background: transparent;
  cursor: pointer;
  font-size: 12px;
  color: #7c3aed;
  padding: 4px 0;
  margin-top: 4px;
  font-family: inherit;

  &:hover {
    text-decoration: underline;
  }
}

.tb-toggle__chevron {
  width: 11px;
  height: 11px;
  stroke: currentColor;
}

.tb-cursor {
  display: inline-block;
  width: 2px;
  height: 15px;
  background: var(--chat-ink);
  margin-left: 2px;
  vertical-align: text-bottom;
  animation: tb-blink 1s infinite;
}

@keyframes tb-blink {
  0%,
  50% {
    opacity: 1;
  }
  51%,
  100% {
    opacity: 0;
  }
}

@keyframes tb-pulse {
  0%,
  100% {
    opacity: 0.5;
  }
  50% {
    opacity: 1;
  }
}
</style>
