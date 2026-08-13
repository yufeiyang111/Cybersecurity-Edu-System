<template>
  <div class="agent-stats-bar">
    <div class="asb-row">
      <button
        type="button"
        class="asb-timer"
        :class="{ 'asb-timer--expanded': open }"
        @click="open = !open"
      >
        <svg class="asb-icon" viewBox="0 0 24 24" fill="none" stroke-width="2">
          <circle cx="12" cy="12" r="10" />
          <polyline points="12 6 12 12 16 14" />
        </svg>
        <span class="asb-timer__text">{{ durationLabel }}</span>
        <svg class="asb-icon asb-timer__chevron" viewBox="0 0 24 24" fill="none" stroke-width="2">
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>
      <span class="asb-divider" />
      <div class="asb-stat">
        <svg class="asb-icon" viewBox="0 0 24 24" fill="none" stroke-width="2">
          <circle cx="12" cy="12" r="10" />
          <path d="M12 6v12" />
          <path d="M15 9.5a2.5 2.5 0 0 0-2.5-2.5h-1a2.5 2.5 0 0 0 0 5h1a2.5 2.5 0 0 1 0 5h-1A2.5 2.5 0 0 1 9 14.5" />
        </svg>
        <span class="asb-stat__label">Tokens</span>
        <span class="asb-stat__value">{{ totalTokensLabel }}</span>
      </div>
      <div class="asb-stat">
        <svg class="asb-icon" viewBox="0 0 24 24" fill="none" stroke-width="2">
          <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
        </svg>
        <span class="asb-stat__label">工具调用</span>
        <span class="asb-stat__value">{{ toolCount }}</span>
      </div>
      <div class="asb-stat">
        <svg class="asb-icon" viewBox="0 0 24 24" fill="none" stroke-width="2">
          <path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96.44 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.24 2.5 2.5 0 0 1 1.98-3A2.5 2.5 0 0 1 9.5 2Z" />
          <path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96.44 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.24 2.5 2.5 0 0 0-1.98-3A2.5 2.5 0 0 0 14.5 2Z" />
        </svg>
        <span class="asb-stat__label">推理轮次</span>
        <span class="asb-stat__value">{{ reasoningRounds }}</span>
      </div>
    </div>

    <div v-if="open" class="asb-detail">
      <div class="asb-detail__title">时间分配</div>
      <div class="asb-detail__grid">
        <div class="asb-detail__item">
          <span class="asb-detail__label">
            <span class="asb-dot asb-dot--thinking" />
            模型思考
          </span>
          <span class="asb-detail__value">{{ thinkingTimeLabel }}</span>
        </div>
        <div class="asb-detail__item">
          <span class="asb-detail__label">
            <span class="asb-dot asb-dot--tool" />
            工具执行
          </span>
          <span class="asb-detail__value">{{ toolTimeLabel }}</span>
        </div>
        <div class="asb-detail__item">
          <span class="asb-detail__label">
            <span class="asb-dot asb-dot--waiting" />
            等待响应
          </span>
          <span class="asb-detail__value">{{ waitingTimeLabel }}</span>
        </div>
        <div class="asb-detail__item">
          <span class="asb-detail__label">
            <svg class="asb-icon asb-icon--sm" viewBox="0 0 24 24" fill="none" stroke-width="2.5">
              <polyline points="20 6 9 17 4 12" />
            </svg>
            工具调用次数
          </span>
          <span class="asb-detail__value">{{ toolCount }} 次</span>
        </div>
      </div>
      <div class="asb-detail__bar">
        <div
          v-if="thinkingRatio > 0"
          class="asb-detail__seg asb-detail__seg--thinking"
          :style="{ width: thinkingRatio + '%' }"
        />
        <div
          v-if="toolRatio > 0"
          class="asb-detail__seg asb-detail__seg--tool"
          :style="{ width: toolRatio + '%' }"
        />
        <div
          v-if="waitingRatio > 0"
          class="asb-detail__seg asb-detail__seg--waiting"
          :style="{ width: waitingRatio + '%' }"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  startedAt: { type: String, default: '' },
  finishedAt: { type: String, default: '' },
  toolCount: { type: Number, default: 0 },
  reasoningRounds: { type: Number, default: 0 },
  totalTokens: { type: Number, default: 0 },
  toolTimeMs: { type: Number, default: 0 },
  thinkingTimeMs: { type: Number, default: 0 },
  waitingTimeMs: { type: Number, default: 0 }
})

const open = ref(false)

function formatDuration(ms) {
  if (!ms || ms <= 0) return '0s'
  const totalSec = Math.floor(ms / 1000)
  const m = Math.floor(totalSec / 60)
  const s = totalSec % 60
  if (m <= 0) return `${s}s`
  return `${m}m ${s.toString().padStart(2, '0')}s`
}

function parseTime(value) {
  if (!value) return 0
  const t = Date.parse(value)
  return Number.isNaN(t) ? 0 : t
}

const totalMs = computed(() => {
  const start = parseTime(props.startedAt)
  const end = parseTime(props.finishedAt)
  if (start && end && end >= start) return end - start
  if (start) return Date.now() - start
  return 0
})

const durationLabel = computed(() => {
  return `已运行 ${formatDuration(totalMs.value)}`
})

const thinkingTimeLabel = computed(() => formatDuration(props.thinkingTimeMs))
const toolTimeLabel = computed(() => formatDuration(props.toolTimeMs))
const waitingTimeLabel = computed(() => formatDuration(props.waitingTimeMs))

const totalTokensLabel = computed(() => {
  if (!props.totalTokens) return '—'
  if (props.totalTokens >= 1000) {
    return `${(props.totalTokens / 1000).toFixed(1)}K`
  }
  return String(props.totalTokens)
})

const allocatable = computed(() => {
  const sum = props.thinkingTimeMs + props.toolTimeMs + props.waitingTimeMs
  return sum > 0 ? sum : totalMs.value
})

const thinkingRatio = computed(() => {
  if (!allocatable.value) return 0
  return Math.round((props.thinkingTimeMs / allocatable.value) * 100)
})
const toolRatio = computed(() => {
  if (!allocatable.value) return 0
  return Math.round((props.toolTimeMs / allocatable.value) * 100)
})
const waitingRatio = computed(() => {
  if (!allocatable.value) return 0
  return Math.max(0, 100 - thinkingRatio.value - toolRatio.value)
})
</script>

<style scoped lang="scss">
.agent-stats-bar {
  border-bottom: 1px solid var(--chat-hairline);
  padding: 10px 0 12px;
  margin-bottom: 8px;
}

.asb-row {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
}

.asb-timer {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: 0;
  background: transparent;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
  color: var(--chat-muted);
  font-family: inherit;

  &:hover {
    background: var(--chat-hover);
    color: var(--chat-ink);
  }
}

.asb-timer__chevron {
  transition: transform 0.2s;
}

.asb-timer--expanded .asb-timer__chevron {
  transform: rotate(180deg);
}

.asb-icon {
  width: 15px;
  height: 15px;
  stroke: var(--chat-hollow);
  flex-shrink: 0;
}

.asb-icon--sm {
  width: 12px;
  height: 12px;
}

.asb-divider {
  width: 1px;
  height: 16px;
  background: var(--chat-hairline-strong);
}

.asb-stat {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--chat-muted);
}

.asb-stat__value {
  font-weight: 600;
  color: var(--chat-ink);
  font-variant-numeric: tabular-nums;
}

.asb-detail {
  margin-top: 12px;
  background: var(--chat-bubble);
  border: 1px solid var(--chat-hairline);
  border-radius: var(--chat-radius);
  padding: 12px 14px;
  animation: asb-slide 0.2s ease;
}

@keyframes asb-slide {
  from {
    opacity: 0;
    transform: translateY(-4px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.asb-detail__title {
  font-size: 11px;
  font-weight: 600;
  color: var(--chat-hollow);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 10px;
}

.asb-detail__grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px 24px;
}

.asb-detail__item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 13px;
}

.asb-detail__label {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--chat-muted);
}

.asb-detail__value {
  font-weight: 600;
  color: var(--chat-ink);
  font-variant-numeric: tabular-nums;
}

.asb-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
}

.asb-dot--thinking {
  background: #a78bfa;
}

.asb-dot--tool {
  background: #60a5fa;
}

.asb-dot--waiting {
  background: #d1d5db;
}

.asb-detail__bar {
  grid-column: 1 / -1;
  height: 6px;
  background: var(--chat-hairline);
  border-radius: 3px;
  overflow: hidden;
  display: flex;
  margin-top: 10px;
}

.asb-detail__seg {
  height: 100%;
  transition: width 0.3s;
}

.asb-detail__seg--thinking {
  background: #a78bfa;
}

.asb-detail__seg--tool {
  background: #60a5fa;
}

.asb-detail__seg--waiting {
  background: #d1d5db;
}
</style>
