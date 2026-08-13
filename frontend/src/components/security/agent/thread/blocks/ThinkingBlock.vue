<template>
  <div class="thinking-block" :class="{ 'thinking-block--live': live }">
    <button
      type="button"
      class="tb-toggle"
      :class="{ 'tb-toggle--open': open }"
      @click="toggle"
    >
      <svg class="tb-toggle__chevron" viewBox="0 0 24 24" fill="none" stroke-width="2">
        <path d="M9 6l6 6-6 6" />
      </svg>
      <span class="tb-toggle__spark" aria-hidden="true">✦</span>
      <span class="tb-toggle__label">{{ title }}</span>
      <span v-if="live" class="tb-toggle__live">思考中…</span>
      <span v-else-if="text" class="tb-toggle__done">已结束</span>
      <span v-if="sensitiveLevel === 'truncated'" class="tb-toggle__trunc">已截断</span>
    </button>
    <div v-if="open" class="tb-panel">
      <pre v-if="text" class="tb-text">{{ text }}</pre>
      <span v-else class="tb-empty">等待模型输出…</span>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  title: { type: String, default: '推理摘要' },
  text: { type: String, default: '' },
  live: { type: Boolean, default: false },
  sensitiveLevel: { type: String, default: 'internal' }
})

const open = ref(false)

function toggle() {
  open.value = !open.value
}

// 实时思考时自动展开；结束后保留用户当前查看状态
watch(
  () => props.live,
  (live) => {
    if (live) open.value = true
  }
)
</script>

<style scoped lang="scss">
.thinking-block {
  margin: 2px 0;
}

.tb-toggle {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  border: 0;
  background: transparent;
  padding: 5px 6px;
  border-radius: 6px;
  font-size: calc(13px * var(--chat-font-scale));
  color: var(--chat-hollow);
  cursor: pointer;
  user-select: none;

  &:hover {
    background: var(--chat-hover);
    color: var(--chat-muted);
  }
}

.tb-toggle--open {
  color: var(--chat-muted);
}

.tb-toggle__chevron {
  width: 12px;
  height: 12px;
  stroke: currentColor;
  transition: transform 0.15s;
}

.tb-toggle--open .tb-toggle__chevron {
  transform: rotate(90deg);
}

.tb-toggle__spark {
  font-size: 11px;
  color: var(--chat-accent);
}

.tb-toggle__label {
  font-weight: 500;
}

.tb-toggle__live {
  font-size: 12px;
  color: var(--chat-accent);
  animation: tb-pulse 1.4s infinite ease-in-out;
}

.tb-toggle__done {
  font-size: 12px;
  color: var(--chat-hollow);
}

.tb-toggle__trunc {
  font-size: 11px;
  color: var(--chat-warning-ink);
  background: var(--chat-warning-bg);
  border-radius: 999px;
  padding: 1px 8px;
}

.tb-panel {
  border-left: 2px solid var(--chat-hairline-strong);
  padding: 4px 0 4px 14px;
  margin: 4px 0 0 24px;
  max-height: 340px;
  overflow-y: auto;
}

.tb-text {
  margin: 0;
  font-family: inherit;
  font-size: calc(13px * var(--chat-font-scale));
  line-height: 1.7;
  color: var(--chat-hollow);
  white-space: pre-wrap;
  word-break: break-word;
}

.tb-empty {
  font-size: 13px;
  color: var(--chat-hollow);
  font-style: italic;
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
