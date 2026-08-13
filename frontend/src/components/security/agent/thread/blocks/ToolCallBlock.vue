<template>
  <div
    class="tool-block"
    :class="[`tool-block--${tool.status}`]"
  >
    <button
      type="button"
      class="tbx-row"
      :disabled="tool.status === 'running'"
      @click="toggle"
    >
      <span class="tbx-icon" aria-hidden="true">
        <span v-if="tool.status === 'running'" class="tbx-spinner" />
        <BaseIcon
          v-else
          :name="tool.status === 'failed' ? 'x' : 'check'"
          :size="12"
        />
      </span>
      <span class="tbx-name">{{ label }}</span>
      <span v-if="tool.status === 'running'" class="tbx-status">执行中</span>
      <span v-else-if="tool.status === 'failed'" class="tbx-status">失败</span>
      <span v-else class="tbx-status">成功</span>
      <span v-if="tool.latency_ms != null" class="tbx-latency">
        {{ tool.latency_ms }} ms
      </span>
      <svg
        v-if="expandable"
        class="tbx-chevron"
        viewBox="0 0 24 24"
        fill="none"
        stroke-width="2"
      >
        <path d="M6 9l6 6 6-6" />
      </svg>
    </button>

    <div v-if="inputText" class="tbx-input">
      <span class="tbx-input__label">输入</span>
      <span class="tbx-input__text">{{ inputText }}</span>
    </div>

    <div v-if="open" class="tbx-detail">
      <div v-if="summary" class="tbx-block">
        <span class="tbx-block__label">结果</span>
        <p class="tbx-block__text">{{ summary }}</p>
      </div>
      <div v-if="tool.error_code" class="tbx-block tbx-block--error">
        <span class="tbx-block__label">错误</span>
        <p class="tbx-block__text">{{ tool.error_code }}</p>
      </div>
      <div v-if="metricsText" class="tbx-block">
        <span class="tbx-block__label">指标</span>
        <pre class="tbx-block__pre">{{ metricsText }}</pre>
      </div>
      <div v-if="tool.artifact_refs?.length" class="tbx-block">
        <span class="tbx-block__label">产物引用</span>
        <p class="tbx-block__text">{{ tool.artifact_refs.join('、') }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { BaseIcon } from '@/components/ui'
import { toolNameLabel } from '@/features/security/agent/statusMeta'

const props = defineProps({
  tool: { type: Object, required: true }
})

const open = ref(false)

const label = computed(() => toolNameLabel(props.tool.tool_name))

const inputText = computed(() => {
  const raw = props.tool.input_summary || props.tool.input_json
  if (!raw) return ''
  if (typeof raw === 'string') return raw
  try {
    return JSON.stringify(raw)
  } catch (e) {
    return String(raw)
  }
})

const summary = computed(() => {
  const raw = props.tool.summary || props.tool.output_summary
  if (!raw) return ''
  if (typeof raw === 'string') return raw
  try {
    return JSON.stringify(raw, null, 2)
  } catch (e) {
    return String(raw)
  }
})

const metricsText = computed(() => {
  if (!props.tool.metrics) return ''
  try {
    return JSON.stringify(props.tool.metrics, null, 2)
  } catch (e) {
    return String(props.tool.metrics)
  }
})

const expandable = computed(() => {
  return Boolean(summary.value || props.tool.error_code || metricsText.value || props.tool.artifact_refs?.length)
})

function toggle() {
  if (!expandable.value) return
  open.value = !open.value
}
</script>

<style scoped lang="scss">
.tool-block {
  border: 1px solid var(--chat-hairline);
  border-radius: var(--chat-radius);
  background: var(--chat-canvas);
  overflow: hidden;
}

.tbx-row {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 12px;
  border: 0;
  background: transparent;
  font-family: inherit;
  text-align: left;
  cursor: pointer;

  &:hover {
    background: var(--chat-hover);
  }

  &:disabled {
    cursor: default;
  }
}

.tbx-icon {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex: none;
}

.tool-block--running .tbx-icon {
  background: var(--chat-accent-soft);
}

.tool-block--running .tbx-icon :deep(svg) {
  stroke: var(--chat-accent);
}

.tool-block--succeeded .tbx-icon {
  background: var(--chat-success-bg);
}

.tool-block--succeeded .tbx-icon :deep(svg) {
  stroke: var(--chat-success-ink);
}

.tool-block--failed .tbx-icon {
  background: var(--chat-danger-bg);
}

.tool-block--failed .tbx-icon :deep(svg) {
  stroke: var(--chat-danger-ink);
}

.tbx-spinner {
  width: 11px;
  height: 11px;
  border: 2px solid var(--chat-accent-border);
  border-top-color: var(--chat-accent);
  border-radius: 50%;
  animation: tbx-spin 0.8s linear infinite;
}

.tbx-name {
  font-size: calc(13.5px * var(--chat-font-scale));
  font-weight: 600;
  color: var(--chat-ink);
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tbx-status {
  font-size: 12px;
  color: var(--chat-hollow);
  flex: none;
}

.tool-block--failed .tbx-status {
  color: var(--chat-danger-ink);
}

.tbx-latency {
  font-size: 12px;
  color: var(--chat-hollow);
  font-variant-numeric: tabular-nums;
  flex: none;
}

.tbx-chevron {
  width: 12px;
  height: 12px;
  stroke: var(--chat-hollow);
  flex: none;
  transition: transform 0.15s;
}

.tool-block:has(.tbx-row:hover) .tbx-chevron {
  stroke: var(--chat-muted);
}

.tbx-input {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  padding: 2px 12px 7px 38px;
  font-size: 12.5px;
  color: var(--chat-hollow);
  line-height: 1.5;
}

.tbx-input__label {
  flex: none;
  font-weight: 600;
}

.tbx-input__text {
  min-width: 0;
  word-break: break-word;
}

.tbx-detail {
  padding: 4px 12px 10px 38px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.tbx-block {
  border-left: 2px solid var(--chat-hairline);
  padding-left: 10px;
}

.tbx-block--error {
  border-left-color: var(--chat-danger-border);
}

.tbx-block__label {
  font-size: 11.5px;
  font-weight: 600;
  color: var(--chat-hollow);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.tbx-block__text {
  margin: 3px 0 0;
  font-size: 13px;
  color: var(--chat-muted);
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}

.tbx-block--error .tbx-block__text {
  color: var(--chat-danger-ink);
}

.tbx-block__pre {
  margin: 3px 0 0;
  font-size: 12px;
  line-height: 1.55;
  color: var(--chat-muted);
  background: var(--chat-hover);
  border-radius: 6px;
  padding: 8px;
  overflow-x: auto;
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
}

@keyframes tbx-spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
