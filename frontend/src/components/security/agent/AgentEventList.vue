<template>
  <section class="events-card">
    <div class="card-head">
      <h2>事件流</h2>
      <span class="note">{{ events.length }} 条（最近）</span>
    </div>
    <el-empty
      v-if="events.length === 0"
      description="暂无事件"
      :image-size="64"
    />
    <ul v-else class="events-list">
      <li v-for="event in events" :key="event.sequence" class="event-row">
        <span class="event-row__icon" :class="`event-row__icon--${toneOf(event).tone}`">
          <BaseIcon :name="toneOf(event).icon" :size="13" />
        </span>
        <div class="event-row__body">
          <div class="event-row__line">
            <span class="event-row__label">{{ toneOf(event).label }}</span>
            <span class="event-row__badge" :class="`event-row__badge--${toneOf(event).tone}`">
              {{ event.event_type }}
            </span>
          </div>
          <div v-if="summaryOf(event)" class="event-row__summary">
            {{ summaryOf(event) }}
          </div>
        </div>
        <span class="event-row__seq">#{{ event.sequence }}</span>
      </li>
    </ul>
  </section>
</template>

<script setup>
import { formatSecurityDate } from '@/features/security/presentation'

defineProps({
  events: { type: Array, default: () => [] }
})

const EVENT_META = {
  'run.created': { icon: 'zap', tone: 'blue', label: '运行创建' },
  'run.state_changed': { icon: 'activity', tone: 'gray', label: '状态变更' },
  'run.paused': { icon: 'clock', tone: 'yellow', label: '运行暂停' },
  'run.resumed': { icon: 'play', tone: 'blue', label: '运行恢复' },
  'run.completed': { icon: 'check', tone: 'green', label: '运行完成' },
  'plan.created': { icon: 'layers', tone: 'blue', label: '计划已生成' },
  'plan.validated': { icon: 'check', tone: 'green', label: '计划已校验' },
  'plan.replanned': { icon: 'layers', tone: 'yellow', label: '计划已重排' },
  'step.started': { icon: 'activity', tone: 'blue', label: '步骤开始' },
  'step.completed': { icon: 'check', tone: 'green', label: '步骤完成' },
  'step.failed': { icon: 'alert-triangle', tone: 'red', label: '步骤失败' },
  'tool.started': { icon: 'code', tone: 'blue', label: '工具调用开始' },
  'tool.progress': { icon: 'activity', tone: 'blue', label: '工具执行中' },
  'tool.completed': { icon: 'check', tone: 'green', label: '工具调用完成' },
  'tool.failed': { icon: 'alert-triangle', tone: 'red', label: '工具调用失败' },
  'llm.started': { icon: 'zap', tone: 'blue', label: 'LLM 调用开始' },
  'llm.usage': { icon: 'coins', tone: 'gray', label: 'LLM 用量' },
  'llm.completed': { icon: 'check', tone: 'green', label: 'LLM 调用完成' },
  'llm.failed': { icon: 'alert-triangle', tone: 'red', label: 'LLM 分析失败' },
  'llm.reasoning_delta': { icon: 'activity', tone: 'gray', label: '思维链增量' },
  'strategy.switched': { icon: 'sliders', tone: 'yellow', label: '策略切换' },
  'decision.recorded': { icon: 'check', tone: 'blue', label: '决策记录' },
  'approval.requested': { icon: 'eye', tone: 'yellow', label: '请求审批' },
  'approval.resolved': { icon: 'check', tone: 'green', label: '审批已处理' },
  'observation.created': { icon: 'eye', tone: 'gray', label: '观察记录' },
  'budget.updated': { icon: 'coins', tone: 'gray', label: '预算更新' },
  'warning.raised': { icon: 'alert-triangle', tone: 'red', label: '告警' },
  'heartbeat': { icon: 'activity', tone: 'gray', label: '心跳' }
}

const DEFAULT_META = { icon: 'activity', tone: 'gray', label: '事件' }

function toneOf(event) {
  return EVENT_META[event.event_type] || DEFAULT_META
}

function summaryOf(event) {
  const payload = event.payload || {}
  switch (event.event_type) {
    case 'plan.created':
      return `v${payload.plan_version} · ${(payload.nodes || []).length} 个节点`
    case 'step.started':
    case 'step.completed':
    case 'step.failed':
      return payload.tool_name ? `工具：${payload.tool_name}` : `节点：${payload.node_key || '-'}`
    case 'tool.started':
    case 'tool.completed':
    case 'tool.failed':
      return payload.tool_name
    case 'llm.usage':
      return payload.tokens ? `${payload.tokens} tokens` : ''
    case 'llm.started':
      return payload.provider ? `${payload.provider}${payload.model ? ' · ' + payload.model : ''}` : ''
    case 'llm.completed':
      return payload.degraded ? '已降级为确定性摘要' : (payload.usage?.tokens ? `${payload.usage.tokens} tokens` : '分析完成')
    case 'llm.failed':
      return payload.agent_warning_code || payload.warning_code || ''
    case 'warning.raised':
      return (payload.warning_codes || []).join('、')
    case 'run.completed':
      return payload.tool_call_count ? `${payload.tool_call_count} 次工具调用` : ''
    case 'run.paused':
    case 'run.resumed':
      return payload.run_id ? `run #${payload.run_id}` : ''
    default:
      return ''
  }
}
</script>

<style scoped lang="scss">
.events-card {
  background: #fff;
  border: 1px solid #e2e7ee;
  border-radius: 8px;
  padding: 14px 16px;
}

.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.card-head h2 {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
}

.card-head .note {
  color: #6a7890;
  font-size: 12.5px;
}

.events-list {
  list-style: none;
  margin: 0;
  padding: 0;
  max-height: 300px;
  overflow-y: auto;
}

.event-row {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 6px 0;
  border-bottom: 1px solid #f4f6f9;
}

.event-row:last-child {
  border-bottom: 0;
}

.event-row__icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 6px;
  flex: none;
  margin-top: 1px;
}

.event-row__icon--blue {
  background: #eff6ff;
  color: #2563eb;
}

.event-row__icon--green {
  background: #dcfce7;
  color: #16a34a;
}

.event-row__icon--red {
  background: #fee2e2;
  color: #dc2626;
}

.event-row__icon--yellow {
  background: #fef9c3;
  color: #ca8a04;
}

.event-row__icon--gray {
  background: #f1f5f9;
  color: #64748b;
}

.event-row__body {
  flex: 1;
  min-width: 0;
}

.event-row__line {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.event-row__label {
  font-size: 12.5px;
  font-weight: 600;
  color: #1f2d3d;
}

.event-row__badge {
  font-size: 10.5px;
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
  border-radius: 4px;
  padding: 1px 5px;
}

.event-row__badge--blue {
  background: #eff6ff;
  color: #2563eb;
}

.event-row__badge--green {
  background: #dcfce7;
  color: #16a34a;
}

.event-row__badge--red {
  background: #fee2e2;
  color: #dc2626;
}

.event-row__badge--yellow {
  background: #fef9c3;
  color: #ca8a04;
}

.event-row__badge--gray {
  background: #f1f5f9;
  color: #64748b;
}

.event-row__summary {
  color: #6a7890;
  font-size: 12px;
  margin-top: 2px;
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
}

.event-row__seq {
  color: #8494a8;
  font-size: 11.5px;
  font-variant-numeric: tabular-nums;
  flex: none;
  margin-top: 2px;
}
</style>
