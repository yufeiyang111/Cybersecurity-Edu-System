<template>
  <BasePanel v-if="project" class="project-inspector">
    <template #header>
      <div class="inspector-head">
        <div class="inspector-title">
          <span class="repo-icon">
            <BaseIcon name="file" :size="17" />
          </span>
          <div>
            <h2>{{ project.name }}</h2>
            <p>{{ project.description || `项目 #${project.id}` }}</p>
          </div>
        </div>
        <div class="state-line">
          <BaseBadge :type="project.is_running ? 'blue' : project.last_scan_at ? 'green' : 'gray'">
            {{ statusLabel }}
          </BaseBadge>
          <span class="health-label">{{ attentionLabel }}</span>
        </div>
      </div>
    </template>

    <section class="inspector-section">
      <h3>项目概况</h3>
      <div class="stats">
        <div>
          <b class="risk">{{ riskTotal }}</b>
          <span>待处理发现</span>
        </div>
        <div>
          <b>{{ project.files ?? 0 }}</b>
          <span>文件数量</span>
        </div>
        <div>
          <b>{{ project.scan_count ?? 0 }}</b>
          <span>扫描次数</span>
        </div>
      </div>
    </section>

    <section class="inspector-section audit-section">
      <h3>发起 Agent 审计</h3>
      <p>审计结果会关联到当前项目快照。</p>
      <textarea
        ref="goalInput"
        v-model="goal"
        maxlength="4000"
        placeholder="输入审计目标（可选）"
      />
      <div class="mode-row">
        <button
          v-for="(meta, key) in agentRunModeMeta"
          :key="key"
          type="button"
          :class="{ active: mode === key }"
          @click="mode = key"
        >
          {{ meta.label }}
        </button>
      </div>
      <BaseButton variant="primary" block :disabled="submitting" @click="submit">
        <BaseIcon name="play" :size="14" />
        {{ submitting ? '创建中…' : '创建审计任务' }}
      </BaseButton>
    </section>

    <section class="inspector-section">
      <h3>
        历史会话
        <span class="section-count">{{ conversations.length }}</span>
      </h3>
      <div v-if="conversationsLoading" class="history-loading">加载中…</div>
      <div v-else-if="conversations.length === 0" class="history-empty">暂无历史会话</div>
      <template v-else>
        <button
          v-for="conversation in conversations"
          :key="conversation.id"
          type="button"
          class="conversation-item"
          @click="$emit('open-conversation', conversation)"
        >
          <span class="conversation-icon">
            <BaseIcon name="history" :size="14" />
          </span>
          <span class="conversation-copy">
            <strong>{{ conversation.title || `会话 #${conversation.id}` }}</strong>
            <small>{{ conversation.turn_sequence }} 轮 · {{ formatDate(conversation.updated_at) }}</small>
          </span>
          <BaseIcon name="arrow-right" :size="14" />
        </button>
      </template>
    </section>

    <section class="inspector-section">
      <h3>最近活动</h3>
      <div class="timeline-item">
        <span class="timeline-dot" :class="{ running: project.is_running }" />
        <div>
          <strong>{{ latestTaskLabel }}</strong>
          <span>{{ latestTaskMeta }}</span>
        </div>
      </div>
    </section>

    <section class="inspector-section inspector-section--last">
      <h3>当前快照</h3>
      <div class="key">
        <span>来源</span>
        <b>{{ project.latest_snapshot_id ? `快照 #${project.latest_snapshot_id}` : '尚未生成' }}</b>
      </div>
      <div class="key">
        <span>最近更新</span>
        <b>{{ formatDate(project.last_scan_at) }}</b>
      </div>
      <BaseButton @click="$emit('view', project)">
        <BaseIcon name="eye" :size="14" />
        打开项目详情
      </BaseButton>
    </section>
  </BasePanel>
  <BasePanel v-else class="project-inspector project-inspector--empty">
    <el-empty description="选择一个项目查看详情" :image-size="56" />
  </BasePanel>
</template>

<script setup>
import { computed, ref } from 'vue'
import { BaseBadge, BaseButton, BaseIcon, BasePanel } from '@/components/ui'
import { agentRunModeMeta } from '@/features/security/agent/statusMeta'

const props = defineProps({
  project: { type: Object, default: null },
  submitting: { type: Boolean, default: false },
  conversations: { type: Array, default: () => [] },
  conversationsLoading: { type: Boolean, default: false }
})

const emit = defineEmits(['start', 'view', 'open-conversation'])
const goal = ref('')
const goalInput = ref(null)
const mode = ref('baseline')

defineExpose({ focusGoal: () => goalInput.value?.focus() })

const riskTotal = computed(() => {
  return ['critical', 'high', 'medium', 'low', 'info'].reduce((total, level) => {
    return total + Number(props.project?.vulns?.[level] || 0)
  }, 0)
})
const statusLabel = computed(() => {
  if (props.project?.is_running) return 'Agent 执行中'
  if (!props.project?.last_scan_at) return '等待审计'
  return props.project.scan_status === 'failed' ? '扫描失败' : '已完成'
})
const attentionLabel = computed(() => riskTotal.value ? '需要关注' : '暂无风险')
const latestTaskLabel = computed(() => props.project?.latest_task_id ? `扫描任务 #${props.project.latest_task_id}` : '暂无 Agent 活动')
const latestTaskMeta = computed(() => {
  if (props.project?.is_running) return '执行中'
  if (props.project?.last_scan_at) return `最近扫描 ${formatDate(props.project.last_scan_at)}`
  return '选择审计模式后创建任务'
})

function submit() {
  if (props.submitting || !props.project) return
  emit('start', { project: props.project, goal: goal.value.trim() || '检查项目安全风险', mode: mode.value })
}

function formatDate(value) {
  if (!value) return '—'
  const date = new Date(value)
  const pad = (number) => String(number).padStart(2, '0')
  return `${date.getMonth() + 1}/${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}
</script>

<style scoped lang="scss">
.project-inspector {
  height: 100%;
  max-height: 100%;
  overflow: auto;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  box-shadow: 0 4px 16px rgba(15, 23, 42, 0.05);
}

.project-inspector :deep(.ui-panel__header) {
  padding: 0;
  background: #fbfcff;
}

.project-inspector :deep(.ui-panel__body) {
  padding: 0 18px 18px;
}

.project-inspector--empty {
  height: auto;
}

.project-inspector--empty :deep(.ui-panel__body) {
  padding: 30px 16px;
}

.inspector-head {
  padding: 17px 18px 14px;
}

.inspector-title {
  display: flex;
  align-items: center;
  gap: 10px;
}

.repo-icon {
  width: 37px;
  height: 37px;
  display: grid;
  place-items: center;
  flex: 0 0 37px;
  border: 1px solid #dbeafe;
  border-radius: 8px;
  color: #2563eb;
  background: #eff6ff;
}

.inspector-title h2 {
  margin: 0;
  color: #172033;
  font-size: 16px;
}

.inspector-title p {
  margin: 3px 0 0;
  overflow: hidden;
  color: #94a3b8;
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.state-line {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 14px;
}

.health-label {
  color: #c94343;
  font-size: 12px;
  font-weight: 600;
}

.inspector-section {
  padding: 16px 0;
  border-bottom: 1px solid #f1f5f9;
}

.inspector-section--last {
  border-bottom: 0;
}

.inspector-section h3 {
  margin: 0 0 10px;
  color: #475569;
  font-size: 13px;
  font-weight: 650;
}

.inspector-section p {
  margin: -4px 0 10px;
  color: #94a3b8;
  font-size: 12px;
}

.stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}

.stats > div {
  padding: 9px 8px;
  border: 1px solid #f1f5f9;
  border-radius: 8px;
  background: #fbfcfe;
  transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease, background 0.2s ease;
}

.stats > div:hover {
  transform: translateY(-2px);
  border-color: #dbeafe;
  background: #fff;
  box-shadow: 0 5px 12px rgba(37, 99, 235, 0.1);
}

.stats b {
  display: block;
  color: #172033;
  font-size: 17px;
  transition: transform 0.2s ease, color 0.2s ease;
}

.stats > div:hover b {
  color: #2563eb;
  transform: scale(1.06);
}

.stats b.risk {
  color: #c94343;
}

.stats span {
  display: block;
  margin-top: 2px;
  color: #94a3b8;
  font-size: 11px;
}

textarea {
  width: 100%;
  min-height: 72px;
  resize: vertical;
  padding: 10px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  outline: 0;
  color: #40506a;
  background: #fff;
  font-size: 12.5px;
  line-height: 1.55;
}

textarea:focus {
  border-color: #93b4f7;
  box-shadow: 0 0 0 3px #eff6ff;
}

textarea::placeholder {
  color: #94a3b8;
}

.mode-row {
  display: flex;
  gap: 6px;
  margin: 8px 0 10px;
}

.mode-row button {
  flex: 1;
  height: 29px;
  padding: 0 3px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  color: #64748b;
  background: #fff;
  font-size: 11.5px;
  transition: transform 0.2s ease, border-color 0.2s ease, color 0.2s ease, background 0.2s ease, box-shadow 0.2s ease;
}

.mode-row button:hover {
  color: #2563eb;
  border-color: #c7d5f7;
  transform: translateY(-1px);
  box-shadow: 0 3px 8px rgba(37, 99, 235, 0.1);
}

.mode-row button:active {
  transform: translateY(0);
}

.mode-row button.active {
  border-color: #bfdbfe;
  color: #2563eb;
  background: #eff6ff;
  font-weight: 600;
}

.timeline-item {
  display: flex;
  align-items: flex-start;
  gap: 9px;
}

.timeline-dot {
  width: 8px;
  height: 8px;
  margin-top: 4px;
  flex: 0 0 8px;
  border-radius: 50%;
  background: #16a34a;
}

.timeline-dot.running {
  background: #2563eb;
  box-shadow: 0 0 0 3px #dbeafe;
  animation: pulse 1.5s ease-in-out infinite;
}

.timeline-item strong {
  display: block;
  color: #475569;
  font-size: 12px;
}

.timeline-item span {
  display: block;
  margin-top: 3px;
  color: #94a3b8;
  font-size: 11px;
}

.key {
  display: flex;
  justify-content: space-between;
  margin-top: 9px;
  color: #64748b;
  font-size: 12px;
}

.key:first-of-type {
  margin-top: 0;
}

.key b {
  color: #40506a;
  font-weight: 600;
}

.inspector-section :deep(.ui-btn) {
  width: 100%;
  margin-top: 12px;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.inspector-section :deep(.ui-btn:hover) {
  transform: translateY(-1px);
  box-shadow: 0 5px 14px rgba(37, 99, 235, 0.18);
}

.inspector-section :deep(.ui-btn:active) {
  transform: translateY(0);
}

.section-count {
  margin-left: 4px;
  color: #94a3b8;
  font-weight: 500;
}

.history-loading,
.history-empty {
  color: #94a3b8;
  font-size: 12px;
}

.conversation-item {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 9px 0;
  border: 0;
  border-bottom: 1px solid #f1f5f9;
  color: #40506a;
  background: transparent;
  text-align: left;
  transition: color 0.2s ease, background 0.2s ease, transform 0.2s ease;
}

.conversation-item:last-child {
  border-bottom: 0;
}

.conversation-item:hover {
  color: #2563eb;
  background: #f8fafc;
  transform: translateX(3px);
}

.conversation-icon {
  width: 26px;
  height: 26px;
  display: grid;
  place-items: center;
  flex: 0 0 26px;
  border-radius: 6px;
  color: #2563eb;
  background: #eff6ff;
  transition: transform 0.24s cubic-bezier(0.34, 1.56, 0.64, 1), background 0.2s ease;
}

.conversation-item:hover .conversation-icon {
  transform: scale(1.1);
  background: #dbeafe;
}

.conversation-copy {
  min-width: 0;
  flex: 1;
}

.conversation-copy strong {
  display: block;
  overflow: hidden;
  font-size: 12.5px;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.conversation-copy small {
  display: block;
  margin-top: 2px;
  color: #94a3b8;
  font-size: 11px;
}

.conversation-item > :deep(.ui-icon) {
  color: #94a3b8;
  transition: transform 0.2s ease, color 0.2s ease;
}

.conversation-item:hover > :deep(.ui-icon) {
  color: #2563eb;
  transform: translateX(2px);
}

@keyframes pulse {
  0%,
  100% {
    opacity: 1;
    transform: scale(1);
  }
  50% {
    opacity: 0.45;
    transform: scale(0.8);
  }
}

@media (max-width: 960px) {
  .project-inspector {
    height: auto;
    max-height: 520px;
  }
}

.project-inspector--empty {
  min-height: 180px;
}

@media (prefers-reduced-motion: reduce) {
  .stats > div,
  .stats b,
  .mode-row button,
  .conversation-item,
  .conversation-icon,
  .conversation-item > :deep(.ui-icon),
  .inspector-section :deep(.ui-btn) {
    transition: none;
  }
  .stats > div:hover,
  .mode-row button:hover,
  .conversation-item:hover,
  .conversation-item:hover .conversation-icon,
  .conversation-item:hover > :deep(.ui-icon),
  .inspector-section :deep(.ui-btn:hover) {
    transform: none;
  }
  .timeline-dot.running {
    animation: none;
  }
}
</style>
