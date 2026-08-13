<template>
  <div class="agent-thread">
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
import ThinkingBlock from './blocks/ThinkingBlock.vue'
import ToolCallBlock from './blocks/ToolCallBlock.vue'
import AssistantBlock from './blocks/AssistantBlock.vue'
import WarningBlock from './blocks/WarningBlock.vue'

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
  fallbackDetail: { type: Array, default: () => [] }
})

const blocks = computed(() => {
  const list = []
  const toolById = {}
  for (const tool of props.toolCalls) {
    toolById[String(tool.id)] = tool
  }

  // 阶段 1：按事件顺序构造 thinking/assistant 块，收集工具调用顺序。
  const toolStartOrder = []
  for (const event of props.events) {
    const type = event.event_type || ''
    const payload = event.payload || {}
    const itemId = event.item_id || payload.item_id || payload.item_public_id || String(event.sequence)
    if (type === 'tool.started') {
      const callId = String(payload.tool_call_id ?? '')
      if (callId) toolStartOrder.push(callId)
    } else if (type === 'item.reasoning_summary.started') {
      list.push({
        kind: 'thinking',
        key: `reasoning-${itemId}`,
        title: '推理摘要',
        text: '',
        live: true,
        sensitiveLevel: payload.sensitive_level || 'internal'
      })
    } else if (type === 'item.reasoning_summary.delta') {
      const existing = list.find(
        (item) =>
          item.kind === 'thinking' &&
          item.key === `reasoning-${itemId}`
      )
      if (existing) {
        existing.text += payload.delta || ''
        existing.live = true
      } else {
        list.push({
          kind: 'thinking',
          key: `reasoning-${itemId}`,
          title: '推理摘要',
          text: payload.delta || '',
          live: true,
          sensitiveLevel: payload.sensitive_level || 'internal'
        })
      }
    } else if (type === 'item.assistant_message.completed') {
      const content =
        payload.content ?? payload.analysis ?? ''
      list.push({
        kind: 'assistant',
        key: `assistant-${event.sequence}`,
        text: content,
        status: props.run?.status || 'completed',
        live: false,
        time: event.occurred_at || ''
      })
    }
  }

  // 实时推理流（无 started 事件时的兜底，来自 SSE reducer 累积）
  if (props.reasoningLive || props.reasoningStream) {
    const liveIdx = list.findIndex((item) => item.kind === 'thinking' && item.live)
    if (liveIdx >= 0) {
      list[liveIdx].text = props.reasoningStream || list[liveIdx].text
      list[liveIdx].live = props.reasoningLive
      list[liveIdx].sensitiveLevel = props.reasoningSensitiveLevel
    } else if (props.reasoningStream) {
      list.push({
        kind: 'thinking',
        key: 'reasoning-live',
        title: '推理摘要',
        text: props.reasoningStream,
        live: props.reasoningLive,
        sensitiveLevel: props.reasoningSensitiveLevel
      })
    }
  }

  // 最终分析兜底（llm.completed 事件或 snapshot 消息）
  if (props.llmAnalysis) {
    const hasAssistant = list.some((item) => item.kind === 'assistant')
    if (!hasAssistant) {
      list.push({
        kind: 'assistant',
        key: 'assistant-final',
        text: props.llmAnalysis,
        status: props.run?.status || 'completed',
        live: false,
        time: props.run?.finished_at || ''
      })
    }
  } else if (props.fallbackText && !props.running) {
    list.push({
      kind: 'assistant',
      key: 'assistant-fallback',
      text: props.fallbackText,
      status: props.run?.status || 'completed',
      live: false,
      time: props.run?.finished_at || ''
    })
  }

  // 警告块（warning_codes 汇总）
  const warningCodes = props.run?.warning_codes || []
  if (warningCodes.length) {
    const warned = list.find((item) => item.kind === 'warning')
    if (!warned) {
      list.push({
        kind: 'warning',
        key: 'warning-final',
        codes: warningCodes
      })
    }
  }

  // 阶段 2：按 tool.started 顺序构造工具块（数据以 store.toolCalls 为准）。
  const toolBlocks = []
  for (const callId of toolStartOrder) {
    const tool = toolById[callId]
    if (tool) {
      toolBlocks.push({
        kind: 'tool',
        key: `tool-${callId}`,
        tool: { ...tool, id: callId }
      })
    }
  }
  for (const tool of props.toolCalls) {
    if (!toolStartOrder.includes(String(tool.id))) {
      toolBlocks.push({
        kind: 'tool',
        key: `tool-snapshot-${tool.id}`,
        tool: { ...tool, id: String(tool.id) }
      })
    }
  }

  // 阶段 3：合并——thinking 块后紧跟其后的工具块（Codex 风格交错），
  // 未跟上的工具块追加到末尾。
  const ordered = []
  let pendingTools = [...toolBlocks]
  for (const block of list) {
    ordered.push(block)
    if (block.kind === 'thinking') {
      const taken = pendingTools.splice(0, pendingTools.length)
      ordered.push(...taken)
    }
  }
  ordered.push(...pendingTools)
  return ordered
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
