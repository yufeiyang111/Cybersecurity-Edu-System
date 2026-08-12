<template>
  <div v-if="toolCalls.length" class="agent-tools">
    <div
      v-for="call in toolCalls"
      :key="call.id"
      class="atc-item"
      :class="[
        `atc-item--${call.status}`,
        { 'atc-item--open': expandedId === call.id }
      ]"
    >
      <button
        type="button"
        class="atc-row"
        :disabled="call.status === 'running'"
        @click="toggleExpand(call.id)"
      >
        <span class="atc-icon" aria-hidden="true">
          <span v-if="call.status === 'running'" class="atc-spinner" />
          <BaseIcon
            v-else
            :name="call.status === 'succeeded' ? 'check' : 'x'"
            :size="13"
          />
        </span>
        <span class="atc-name">{{ callLabel(call) }}</span>
        <span v-if="call.status === 'running'" class="atc-status">执行中</span>
        <span v-else-if="call.status === 'failed'" class="atc-status">失败</span>
        <span v-else class="atc-status">成功</span>
        <span v-if="call.latency_ms != null" class="atc-latency">{{ call.latency_ms }} ms</span>
        <svg
          v-if="expandable(call)"
          class="atc-chevron"
          viewBox="0 0 24 24"
          fill="none"
          stroke-width="2"
        >
          <path d="M6 9l6 6 6-6" />
        </svg>
      </button>

      <div v-if="call.input_summary" class="atc-input">
        <span class="atc-input__label">输入</span>
        <span class="atc-input__text">{{ call.input_summary }}</span>
      </div>

      <div v-if="expandedId === call.id" class="atc-detail">
        <div v-if="call.output_summary" class="atc-detail__block">
          <span class="atc-detail__label">结果</span>
          <p class="atc-detail__text">{{ call.output_summary }}</p>
        </div>
        <div v-if="call.error_code" class="atc-detail__block atc-detail__block--error">
          <span class="atc-detail__label">错误</span>
          <p class="atc-detail__text">{{ call.error_code }}</p>
        </div>
        <div v-if="metricsTextOf(call)" class="atc-detail__block">
          <span class="atc-detail__label">指标</span>
          <pre class="atc-detail__pre">{{ metricsTextOf(call) }}</pre>
        </div>
        <div v-if="call.artifact_refs?.length" class="atc-detail__block">
          <span class="atc-detail__label">产物引用</span>
          <p class="atc-detail__text">{{ call.artifact_refs.join('、') }}</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { BaseIcon } from '@/components/ui'
import { toolNameLabel } from '@/features/security/agent/statusMeta'

defineProps({
  toolCalls: { type: Array, default: () => [] }
})

const expandedId = ref(null)

function callLabel(call) {
  return toolNameLabel(call.tool_name)
}

function toggleExpand(id) {
  expandedId.value = expandedId.value === id ? null : id
}

function expandable(call) {
  return Boolean(
    call.output_summary ||
    call.summary ||
    call.error_code ||
    call.metrics ||
    call.artifact_refs?.length
  )
}

const metricsTextOf = (call) => {
  if (!call.metrics) return ''
  try {
    return JSON.stringify(call.metrics, null, 2)
  } catch (e) {
    return String(call.metrics)
  }
}
</script>

<style scoped lang="scss">
.agent-tools {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 10px;
}

.atc-item {
  border: 1px solid var(--chat-hairline);
  border-radius: var(--chat-radius);
  background: var(--chat-canvas);
  overflow: hidden;
}

.atc-item--open {
  border-color: var(--chat-hairline-strong);
}

.atc-row {
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

.atc-icon {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex: none;
}

.atc-item--running .atc-icon {
  background: var(--chat-accent-soft);
}

.atc-item--running .atc-icon :deep(svg) {
  stroke: var(--chat-accent);
}

.atc-item--succeeded .atc-icon {
  background: var(--chat-success-bg);
}

.atc-item--succeeded .atc-icon :deep(svg) {
  stroke: var(--chat-success-ink);
}

.atc-item--failed .atc-icon {
  background: var(--chat-danger-bg);
}

.atc-item--failed .atc-icon :deep(svg) {
  stroke: var(--chat-danger-ink);
}

.atc-spinner {
  width: 11px;
  height: 11px;
  border: 2px solid var(--chat-accent-border);
  border-top-color: var(--chat-accent);
  border-radius: 50%;
  animation: atc-spin 0.8s linear infinite;
}

.atc-name {
  font-size: calc(13.5px * var(--chat-font-scale));
  font-weight: 600;
  color: var(--chat-ink);
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.atc-status {
  font-size: 12px;
  color: var(--chat-hollow);
  flex: none;
}

.atc-item--failed .atc-status {
  color: var(--chat-danger-ink);
}

.atc-latency {
  font-size: 12px;
  color: var(--chat-hollow);
  font-variant-numeric: tabular-nums;
  flex: none;
}

.atc-chevron {
  width: 12px;
  height: 12px;
  stroke: var(--chat-hollow);
  flex: none;
  transition: transform 0.15s;
}

.atc-item--open .atc-chevron {
  transform: rotate(180deg);
}

.atc-input {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  padding: 2px 12px 7px 38px;
  font-size: 12.5px;
  color: var(--chat-hollow);
  line-height: 1.5;
}

.atc-input__label {
  flex: none;
  font-weight: 600;
  color: var(--chat-hollow);
}

.atc-input__text {
  min-width: 0;
  word-break: break-word;
}

.atc-detail {
  padding: 4px 12px 10px 38px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.atc-detail__block {
  border-left: 2px solid var(--chat-hairline);
  padding-left: 10px;
}

.atc-detail__block--error {
  border-left-color: var(--chat-danger-border);
}

.atc-detail__label {
  font-size: 11.5px;
  font-weight: 600;
  color: var(--chat-hollow);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.atc-detail__text {
  margin: 3px 0 0;
  font-size: 13px;
  color: var(--chat-muted);
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}

.atc-detail__block--error .atc-detail__text {
  color: var(--chat-danger-ink);
}

.atc-detail__pre {
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

@keyframes atc-spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
