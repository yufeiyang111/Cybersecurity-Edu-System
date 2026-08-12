<template>
  <div class="agent-thinking" :class="{ 'agent-thinking--live': live }">
    <button
      class="at-toggle"
      :class="{ open }"
      type="button"
      @click="toggle"
    >
      <svg
        class="at-toggle__chevron"
        viewBox="0 0 24 24"
        fill="none"
        stroke-width="2"
      >
        <path d="M9 6l6 6-6 6" />
      </svg>
      <svg
        class="at-toggle__spark"
        viewBox="0 0 24 24"
        fill="none"
        stroke-width="2"
      >
        <path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9L12 3z" />
      </svg>
      <span class="at-toggle__label">思考过程</span>
      <span v-if="live" class="at-toggle__live">思考中…</span>
      <span v-else-if="text" class="at-toggle__done">已结束</span>
    </button>
    <div v-if="open" class="at-panel">
      <pre v-if="text" class="at-text">{{ text }}</pre>
      <span v-else class="at-empty">等待模型输出…</span>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  text: { type: String, default: '' },
  live: { type: Boolean, default: false }
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
.agent-thinking {
  margin-bottom: 4px;
}

.at-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: 0;
  background: transparent;
  padding: 4px 0;
  font-size: calc(13px * var(--chat-font-scale));
  color: var(--chat-hollow);
  cursor: pointer;
  user-select: none;
  opacity: 0.85;

  &:hover {
    opacity: 1;
  }
}

.at-toggle__chevron {
  width: 12px;
  height: 12px;
  stroke: var(--chat-hollow);
  transition: transform 0.15s;
}

.at-toggle.open .at-toggle__chevron {
  transform: rotate(90deg);
}

.at-toggle__spark {
  width: 12px;
  height: 12px;
  stroke: var(--chat-hollow);
  display: none;
}

.at-toggle__label {
  font-weight: 500;
  color: var(--chat-muted);
}

.at-toggle__live {
  font-size: 12px;
  color: var(--chat-accent);
  animation: at-pulse 1.4s infinite ease-in-out;
}

.at-toggle__done {
  font-size: 12px;
  color: var(--chat-hollow);
}

.at-panel {
  border-left: 2px solid var(--chat-hairline-strong);
  padding: 2px 0 2px 14px;
  margin-top: 4px;
  max-height: 320px;
  overflow-y: auto;
}

.at-text {
  margin: 0;
  font-family: inherit;
  font-size: calc(13px * var(--chat-font-scale));
  line-height: 1.7;
  color: var(--chat-hollow);
  font-style: italic;
  white-space: pre-wrap;
  word-break: break-word;
}

.at-empty {
  font-size: 13px;
  color: var(--chat-hollow);
  font-style: italic;
}

@keyframes at-pulse {
  0%, 100% {
    opacity: 0.5;
  }
  50% {
    opacity: 1;
  }
}
</style>
