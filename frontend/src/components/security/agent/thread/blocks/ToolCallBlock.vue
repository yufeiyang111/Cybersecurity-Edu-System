<template>
  <div
    class="tool-block"
    :class="[`tool-block--${tool.status}`, { 'tool-block--expanded': open }]"
  >
    <button
      type="button"
      class="tbx-header"
      :disabled="tool.status === 'running'"
      @click="toggle"
    >
      <span class="tbx-icon" aria-hidden="true">
        <span v-if="tool.status === 'running'" class="tbx-spinner" />
        <svg
          v-else-if="tool.status === 'failed'"
          viewBox="0 0 24 24"
          fill="none"
          stroke-width="2.5"
        >
          <line x1="18" y1="6" x2="6" y2="18" />
          <line x1="6" y1="6" x2="18" y2="18" />
        </svg>
        <svg v-else viewBox="0 0 24 24" fill="none" stroke-width="2.5">
          <polyline points="20 6 9 17 4 12" />
        </svg>
      </span>
      <span class="tbx-name">{{ label }}</span>
      <span v-if="targetText" class="tbx-target">{{ targetText }}</span>
      <span v-if="tool.status === 'running'" class="tbx-status">执行中…</span>
      <span v-else-if="tool.status === 'failed'" class="tbx-status">失败</span>
      <span v-if="latencyText" class="tbx-latency">{{ latencyText }}</span>
      <svg
        v-if="expandable"
        class="tbx-chevron"
        viewBox="0 0 24 24"
        fill="none"
        stroke-width="2"
      >
        <polyline points="6 9 12 15 18 9" />
      </svg>
    </button>

    <div v-if="open" class="tbx-detail">
      <div v-if="inputText" class="tbx-section">
        <span class="tbx-section__label">输入参数</span>
        <div class="tbx-section__value tbx-section__value--mono">{{ inputText }}</div>
      </div>
      <div v-if="summary" class="tbx-section">
        <span class="tbx-section__label">结果</span>
        <div
          class="tbx-section__value"
          :class="{ 'tbx-section__value--success': tool.status !== 'failed' }"
        >
          {{ summary }}
        </div>
      </div>
      <div v-if="tool.error_code" class="tbx-section">
        <span class="tbx-section__label">错误</span>
        <div class="tbx-section__value tbx-section__value--error">{{ tool.error_code }}</div>
      </div>
      <div v-if="metricsText" class="tbx-section">
        <span class="tbx-section__label">指标</span>
        <pre class="tbx-section__pre">{{ metricsText }}</pre>
      </div>
      <div v-if="tool.artifact_refs?.length" class="tbx-section">
        <span class="tbx-section__label">产物引用</span>
        <div class="tbx-section__value">{{ tool.artifact_refs.join('、') }}</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { toolNameLabel } from '@/features/security/agent/statusMeta'

const props = defineProps({
  tool: { type: Object, required: true }
})

const open = ref(false)

const label = computed(() => toolNameLabel(props.tool.tool_name))

const targetText = computed(() => {
  const raw = props.tool.input_summary || props.tool.input_json
  if (!raw) return ''
  if (typeof raw === 'string') return raw
  try {
    return JSON.stringify(raw).slice(0, 80)
  } catch (e) {
    return String(raw).slice(0, 80)
  }
})

const inputText = computed(() => {
  const raw = props.tool.input_summary || props.tool.input_json
  if (!raw) return ''
  if (typeof raw === 'string') return raw
  try {
    return JSON.stringify(raw, null, 2)
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

const latencyText = computed(() => {
  if (props.tool.status === 'running') return ''
  if (props.tool.latency_ms != null) {
    if (props.tool.latency_ms >= 1000) {
      return `${(props.tool.latency_ms / 1000).toFixed(1)}s`
    }
    return `${props.tool.latency_ms}ms`
  }
  return ''
})

const expandable = computed(() => {
  return Boolean(
    inputText.value ||
    summary.value ||
    props.tool.error_code ||
    metricsText.value ||
    props.tool.artifact_refs?.length
  )
})

function toggle() {
  if (!expandable.value) return
  open.value = !open.value
}
</script>

<style scoped lang="scss">
.tool-block {
  margin: 2px 0 12px;
  animation: tbx-fade 0.3s ease;
}

@keyframes tbx-fade {
  from {
    opacity: 0;
    transform: translateY(4px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.tbx-header {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 10px;
  border: 1px solid var(--chat-hairline);
  border-radius: var(--chat-radius);
  background: var(--chat-bubble);
  font-family: inherit;
  text-align: left;
  cursor: pointer;
  transition: background 0.15s;

  &:hover {
    background: var(--chat-hover);
  }

  &:disabled {
    cursor: default;
  }
}

.tool-block--running .tbx-header {
  background: var(--chat-accent-soft);
  border-color: var(--chat-accent-border);
}

.tool-block--failed .tbx-header {
  background: var(--chat-danger-bg);
  border-color: var(--chat-danger-border);
}

.tool-block--expanded .tbx-header {
  border-radius: var(--chat-radius) var(--chat-radius) 0 0;
}

.tbx-icon {
  width: 18px;
  height: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  color: var(--chat-hollow);
}

.tbx-icon svg {
  width: 13px;
  height: 13px;
  stroke: currentColor;
}

.tool-block--running .tbx-icon {
  color: var(--chat-accent);
}

.tool-block--failed .tbx-icon {
  color: var(--chat-danger-ink);
}

.tool-block--succeeded .tbx-icon {
  color: var(--chat-success-ink);
}

.tbx-spinner {
  width: 13px;
  height: 13px;
  border: 2px solid var(--chat-accent-border);
  border-top-color: var(--chat-accent);
  border-radius: 50%;
  animation: tbx-spin 0.8s linear infinite;
}

.tbx-name {
  font-size: calc(13.5px * var(--chat-font-scale));
  font-weight: 500;
  color: var(--chat-ink);
  flex-shrink: 0;
}

.tool-block--running .tbx-name {
  color: var(--chat-accent);
}

.tbx-target {
  font-size: 12px;
  color: var(--chat-hollow);
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
  max-width: 260px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  min-width: 0;
}

.tbx-status {
  font-size: 12px;
  color: var(--chat-hollow);
  flex-shrink: 0;
}

.tool-block--failed .tbx-status {
  color: var(--chat-danger-ink);
}

.tbx-latency {
  margin-left: auto;
  font-size: 12px;
  color: var(--chat-hollow);
  font-variant-numeric: tabular-nums;
  flex-shrink: 0;
}

.tbx-chevron {
  width: 14px;
  height: 14px;
  stroke: var(--chat-hollow);
  flex-shrink: 0;
  transition: transform 0.2s;
}

.tool-block--expanded .tbx-chevron {
  transform: rotate(180deg);
}

.tbx-detail {
  padding: 12px 14px;
  background: var(--chat-canvas);
  border: 1px solid var(--chat-hairline);
  border-top: none;
  border-radius: 0 0 var(--chat-radius) var(--chat-radius);
  font-size: 13px;
  animation: tbx-slide 0.2s ease;
}

@keyframes tbx-slide {
  from {
    opacity: 0;
    transform: translateY(-4px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.tbx-section {
  margin-bottom: 10px;
}

.tbx-section:last-child {
  margin-bottom: 0;
}

.tbx-section__label {
  font-size: 10px;
  font-weight: 600;
  color: var(--chat-hollow);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 4px;
  display: block;
}

.tbx-section__value {
  color: var(--chat-muted);
  line-height: 1.55;
  white-space: pre-wrap;
  word-break: break-word;
}

.tbx-section__value--mono {
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
  font-size: 12px;
  color: var(--chat-ink);
}

.tbx-section__value--success {
  color: var(--chat-success-ink);
}

.tbx-section__value--error {
  color: var(--chat-danger-ink);
}

.tbx-section__pre {
  margin: 0;
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
  font-size: 12px;
  line-height: 1.55;
  color: var(--chat-muted);
  background: var(--chat-hover);
  border-radius: 6px;
  padding: 8px;
  overflow-x: auto;
}

@keyframes tbx-spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
