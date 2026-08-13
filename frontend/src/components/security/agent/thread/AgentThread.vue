<template>
  <div class="agent-thread">
    <AgentStatsBar
      v-if="run"
      :started-at="run.started_at"
      :finished-at="run.finished_at"
      :tool-count="toolCount"
      :reasoning-rounds="reasoningRounds"
      :total-tokens="totalTokens"
      :tool-time-ms="toolTimeMs"
      :thinking-time-ms="thinkingTimeMs"
      :waiting-time-ms="waitingTimeMs"
    />

    <!-- 用户消息 -->
    <div
      v-for="userMsg in userMessages"
      :key="`user-${userMsg.key}`"
      class="at-msg at-msg--user"
    >
      <div class="at-user-bubble">{{ userMsg.text }}</div>
    </div>

    <!-- 交错块：思考 / 工具 / 助手 按事件顺序 -->
    <template v-for="block in blocks" :key="block.key">
      <ThinkingBlock
        v-if="block.kind === 'thinking'"
        :title="block.title"
        :text="block.text"
        :live="block.live"
        :sensitive-level="block.sensitiveLevel"
      />
      <ToolCallBlock
        v-else-if="block.kind === 'tool'"
        :tool="block.tool"
      />
      <AssistantBlock
        v-else-if="block.kind === 'assistant'"
        :text="block.text"
        :status="block.status"
        :live="block.live"
        :time="block.time"
      />
      <WarningBlock
        v-else-if="block.kind === 'warning'"
        :codes="block.codes"
      />
    </template>

    <div v-if="running && !blocks.length" class="at-running">
      <span class="at-running__dot" />
      Agent 正在执行…
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import AgentStatsBar from './AgentStatsBar.vue'
import ThinkingBlock from './blocks/ThinkingBlock.vue'
import ToolCallBlock from './blocks/ToolCallBlock.vue'
import AssistantBlock from './blocks/AssistantBlock.vue'
import WarningBlock from './blocks/WarningBlock.vue'
import { buildThreadBlocks } from '@/features/security/agent/threadBlocks'

const props = defineProps({
  userMessages: { type: Array, default: () => [] },
  events: { type: Array, default: () => [] },
  toolCalls: { type: Array, default: () => [] },
  reasoningStream: { type: String, default: '' },
  reasoningLive: { type: Boolean, default: false },
  reasoningSensitiveLevel: { type: String, default: 'internal' },
  llmAnalysis: { type: String, default: '' },
  run: { type: Object, default: null },
  running: { type: Boolean, default: false },
  fallbackText: { type: String, default: '' },
  fallbackDetail: { type: Array, default: () => [] },
  totalTokens: { type: Number, default: 0 }
})

// 顶部统计：工具调用次数
const toolCount = computed(() => props.toolCalls.length)

// 推理轮次 = 独立 reasoning_summary 块数量
const reasoningRounds = computed(() => {
  return props.events.filter(
    (event) => (event.event_type || '') === 'item.reasoning_summary.started'
  ).length
})

// 工具执行总耗时（tool.completed latency 求和）
const toolTimeMs = computed(() => {
  return props.toolCalls.reduce((sum, tool) => {
    const latency = Number(tool.latency_ms)
    return sum + (Number.isFinite(latency) && latency > 0 ? latency : 0)
  }, 0)
})

// 模型思考耗时（估算：推理轮次 × 8s，无精确数据时给合理估算）
const thinkingTimeMs = computed(() => {
  const rounds = reasoningRounds.value
  if (!rounds) return 0
  return rounds * 8000
})

// 等待时间 = 总时长 - 工具耗时 - 思考耗时（下限 0）
const waitingTimeMs = computed(() => {
  const start = Date.parse(props.run?.started_at || '')
  const end = Date.parse(props.run?.finished_at || '')
  const total = start && end && end >= start ? end - start : 0
  return Math.max(0, total - toolTimeMs.value - thinkingTimeMs.value)
})

const blocks = computed(() => {
  // 单一事件驱动：thinking / tool / assistant 全部按事件 sequence 交错。
  // 每个块携带 seq，最后统一排序——保证思考与工具调用严格按时间顺序。
  // 非 live 且无文本的 thinking 块（started 后 delta 全被脱敏丢弃）不渲染。
  return buildThreadBlocks({
    events: props.events,
    toolCalls: props.toolCalls,
    reasoningStream: props.reasoningStream,
    reasoningLive: props.reasoningLive,
    reasoningSensitiveLevel: props.reasoningSensitiveLevel,
    llmAnalysis: props.llmAnalysis,
    run: props.run,
    running: props.running,
    fallbackText: props.fallbackText,
    fallbackDetail: props.fallbackDetail
  }).filter((block) => {
    if (block.kind === 'thinking' && !block.live && !(block.text || '').trim()) {
      return false
    }
    return true
  })
})
</script>

<style scoped lang="scss">
.agent-thread {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.at-msg--user {
  display: flex;
  justify-content: flex-end;
}

.at-user-bubble {
  max-width: 68%;
  background: var(--chat-bubble);
  border-radius: var(--chat-radius);
  padding: calc(12px * var(--chat-space-scale)) calc(16px * var(--chat-space-scale));
  font-size: calc(15px * var(--chat-font-scale));
  line-height: 1.6;
}

.at-running {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 0;
  font-size: 13px;
  color: var(--chat-hollow);
}

.at-running__dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--chat-accent);
  animation: at-pulse 1.4s infinite ease-in-out;
}

@keyframes at-pulse {
  0%,
  100% {
    opacity: 0.4;
  }
  50% {
    opacity: 1;
  }
}
</style>
