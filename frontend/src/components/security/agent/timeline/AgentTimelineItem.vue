<template>
  <div class="timeline-item" :class="`timeline-item--${item.itemType}`">
    <div class="timeline-item__marker">
      <BaseIcon :name="markerIcon" :size="13" />
    </div>
    <div class="timeline-item__body">
      <div class="timeline-item__meta">
        <span class="timeline-item__type">{{ typeLabel }}</span>
        <BaseBadge
          v-if="item.status"
          :type="statusBadge"
          size="small"
        >
          {{ statusLabel }}
        </BaseBadge>
        <span
          v-if="item.errorCode"
          class="timeline-item__error"
        >
          {{ item.errorCode }}
        </span>
      </div>

      <div v-if="item.content" class="timeline-item__content">
        {{ item.content }}
      </div>

      <div
        v-if="item.itemType === 'reasoning_summary' && item.content"
        class="timeline-item__reasoning"
      >
        推理摘要：{{ item.content }}
      </div>

      <div
        v-if="item.itemType === 'tool_call' && item.summary"
        class="timeline-item__tool"
      >
        <span v-if="item.summary.name">工具：{{ item.summary.name }}</span>
        <span v-if="item.summary.summary" class="timeline-item__tool-summary">
          {{ item.summary.summary }}
        </span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { BaseBadge, BaseIcon } from '@/components/ui'

const props = defineProps({
  item: { type: Object, required: true }
})

const TYPE_LABELS = {
  user_message: '用户',
  intent_summary: '意图',
  plan: '计划',
  decision: '决策',
  decision_summary: '决策',
  reasoning_summary: '推理摘要',
  tool_call: '工具调用',
  tool_result: '工具结果',
  observation: '观察',
  approval: '审批',
  assistant_message: '助手',
  controller_feedback: '控制器反馈',
  warning: '警告'
}

const MARKER_ICONS = {
  user_message: 'user',
  intent_summary: 'target',
  plan: 'list',
  decision: 'decision',
  decision_summary: 'decision',
  reasoning_summary: 'spark',
  tool_call: 'tool',
  tool_result: 'result',
  observation: 'eye',
  approval: 'approval',
  assistant_message: 'robot',
  controller_feedback: 'shield',
  warning: 'warning'
}

const typeLabel = computed(() => TYPE_LABELS[props.item.itemType] || props.item.itemType)
const markerIcon = computed(() => MARKER_ICONS[props.item.itemType] || 'spark')

const statusBadge = computed(() => {
  if (props.item.status === 'failed') return 'red'
  if (props.item.status === 'completed') return 'green'
  if (props.item.status === 'streaming') return 'blue'
  return 'gray'
})

const statusLabel = computed(() => {
  if (props.item.status === 'failed') return '失败'
  if (props.item.status === 'completed') return '完成'
  if (props.item.status === 'streaming') return '进行中'
  return props.item.status || ''
})
</script>

<style scoped lang="scss">
.timeline-item {
  display: flex;
  gap: 10px;
  padding: 8px 0;
  align-items: flex-start;
}

.timeline-item__marker {
  width: 24px;
  height: 24px;
  border-radius: 999px;
  background: var(--chat-accent-soft, #eff6ff);
  color: var(--chat-accent, #2563eb);
  display: flex;
  align-items: center;
  justify-content: center;
  flex: none;
  margin-top: 2px;
}

.timeline-item--warning .timeline-item__marker {
  background: var(--chat-warning-bg, #fef3c7);
  color: var(--chat-warning-ink, #b45309);
}

.timeline-item--assistant_message .timeline-item__marker {
  background: var(--chat-success-bg, #ecfdf5);
  color: var(--chat-success-ink, #047857);
}

.timeline-item--user_message .timeline-item__marker {
  background: var(--chat-hover, #eef2f7);
  color: var(--chat-hollow, #8494a8);
}

.timeline-item__body {
  flex: 1;
  min-width: 0;
}

.timeline-item__meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 3px;
}

.timeline-item__type {
  font-size: 12px;
  font-weight: 600;
  color: var(--chat-muted, #6a7890);
}

.timeline-item__error {
  font-size: 11.5px;
  color: var(--chat-danger-ink, #b91c1c);
}

.timeline-item__content {
  font-size: 13.5px;
  color: var(--chat-ink, #1f2d3d);
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}

.timeline-item__reasoning {
  font-size: 12.5px;
  color: var(--chat-hollow, #8494a8);
  font-style: italic;
  line-height: 1.6;
}

.timeline-item__tool {
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: 12.5px;
  color: var(--chat-muted, #6a7890);
}

.timeline-item__tool-summary {
  color: var(--chat-ink, #1f2d3d);
}
</style>
