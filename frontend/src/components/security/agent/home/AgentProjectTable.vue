<template>
  <section class="project-table" aria-label="Agent 项目列表">
    <div class="table-header">
      <h2>项目列表</h2>
      <span>{{ projects.length }} 个项目</span>
    </div>

    <div v-if="loading" class="table-loading">
      <el-skeleton v-for="index in 5" :key="index" :rows="1" animated />
    </div>
    <el-empty v-else-if="projects.length === 0" description="没有符合条件的项目" :image-size="56" />
    <div v-else class="table-scroll">
      <section v-for="section in sections" :key="section.key" v-show="section.items.length" class="project-group">
        <div class="group-title">
          <span>{{ section.label }}</span>
          <span class="group-count">{{ section.items.length }} 个项目</span>
        </div>
        <div class="table-head" role="row">
          <span>项目</span>
          <span>语言</span>
          <span>最近扫描</span>
          <span>风险</span>
          <span>最近 Agent 活动</span>
          <span class="actions-head">操作</span>
        </div>
        <button
          v-for="project in section.items"
          :key="project.id"
          type="button"
          class="project-row"
          :class="{ selected: selectedProjectId === project.id }"
          @click="$emit('select', project)"
        >
          <span class="project-identity">
            <span class="repo-icon">
              <BaseIcon name="file" :size="15" />
            </span>
            <span class="identity-copy">
              <strong>{{ project.name }}</strong>
              <small>{{ project.description || `项目 #${project.id}` }}</small>
            </span>
          </span>
          <span class="language">{{ languageMeta(project.language).label }}</span>
          <span class="scan-time">
            {{ formatRelativeDate(project.last_scan_at) }}
            <small>{{ formatDate(project.last_scan_at) }}</small>
          </span>
          <span class="risk-list" :aria-label="riskLabel(project)">
            <span v-if="severityCount(project, 'critical')" class="critical">
              <i />
              {{ severityCount(project, 'critical') }}
            </span>
            <span v-if="severityCount(project, 'high')" class="high">
              <i />
              {{ severityCount(project, 'high') }}
            </span>
            <span v-if="severityCount(project, 'medium')" class="medium">
              <i />
              {{ severityCount(project, 'medium') }}
            </span>
            <span v-if="riskTotal(project) === 0" class="low">
              <i />
              {{ project.last_scan_at ? '0' : '—' }}
            </span>
          </span>
          <span class="agent-activity">
            <BaseIcon name="activity" :size="14" />
            <span>
              <strong>{{ latestActivity(project) }}</strong>
              <small :class="activityClass(project)">
                <i />
                {{ statusLabel(project) }}
              </small>
            </span>
          </span>
          <span class="row-actions">
            <span
              class="icon-button primary"
              title="开始审计"
              @click.stop="$emit('start', project)"
            >
              <BaseIcon name="play" :size="14" />
            </span>
            <span class="icon-button" title="查看项目" @click.stop="$emit('view', project)">
              <BaseIcon name="eye" :size="14" />
            </span>
          </span>
        </button>
      </section>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { BaseIcon } from '@/components/ui'
import { languageMeta } from '@/features/security/languageMeta'

const props = defineProps({
  projects: { type: Array, default: () => [] },
  selectedProjectId: { type: [Number, String], default: null },
  loading: { type: Boolean, default: false }
})

defineEmits(['select', 'start', 'view'])

const sectionMeta = [
  { key: 'running', label: '正在运行' },
  { key: 'attention', label: '需要关注' },
  { key: 'recent', label: '最近活动' },
  { key: 'unscanned', label: '尚未扫描' }
]

const sections = computed(() => sectionMeta.map((section) => ({
  ...section,
  items: props.projects.filter((project) => projectGroup(project) === section.key)
})))

function projectGroup(project) {
  if (project.is_running) return 'running'
  if (riskTotal(project) > 0) return 'attention'
  if (!project.last_scan_at) return 'unscanned'
  return 'recent'
}

function severityCount(project, level) {
  return Number(project.vulns?.[level] || 0)
}

function riskTotal(project) {
  return ['critical', 'high', 'medium', 'low', 'info'].reduce((total, level) => total + severityCount(project, level), 0)
}

function riskLabel(project) {
  return `${riskTotal(project)} 个风险`
}

function statusLabel(project) {
  if (project.is_running) return '执行中'
  if (!project.last_scan_at) return '等待审计'
  if (project.scan_status === 'failed') return '失败'
  if (project.scan_status === 'canceled') return '已取消'
  return '已完成'
}

function activityClass(project) {
  if (project.is_running) return 'running'
  if (!project.last_scan_at) return 'none'
  return 'done'
}

function latestActivity(project) {
  if (!project.latest_task_id) return '暂无 Agent 活动'
  return `扫描任务 #${project.latest_task_id}`
}

function formatRelativeDate(value) {
  if (!value) return '未扫描'
  const diff = Date.now() - new Date(value).getTime()
  const hours = Math.max(0, Math.floor(diff / 3600000))
  if (hours < 1) return '刚刚'
  if (hours < 24) return `${hours} 小时前`
  const days = Math.floor(hours / 24)
  return days < 7 ? `${days} 天前` : '较早'
}

function formatDate(value) {
  if (!value) return '—'
  const date = new Date(value)
  const pad = (number) => String(number).padStart(2, '0')
  return `${date.getMonth() + 1}/${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}
</script>

<style scoped lang="scss">
.project-table {
  min-width: 0;
  height: 100%;
  overflow: hidden;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #fff;
  box-shadow: 0 4px 16px rgba(15, 23, 42, 0.05);
}

.table-header {
  position: sticky;
  top: 0;
  z-index: 2;
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 50px;
  padding: 0 18px;
  border-bottom: 1px solid #f1f5f9;
  background: rgba(255, 255, 255, 0.96);
  backdrop-filter: blur(8px);
}

.table-header h2 {
  margin: 0;
  color: #172033;
  font-size: 15px;
  font-weight: 650;
}

.table-header > span {
  color: #94a3b8;
  font-size: 12px;
}

.table-scroll {
  height: calc(100% - 50px);
  overflow: auto;
}

.table-loading {
  padding: 16px;
}

.table-loading :deep(.el-skeleton) {
  margin-bottom: 14px;
}

.project-group + .project-group {
  margin-top: 12px;
}

.group-title {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 34px;
  padding: 0 18px;
  color: #475569;
  background: #f8fafc;
  font-size: 12px;
  font-weight: 650;
}

.group-count {
  color: #94a3b8;
  font-weight: 500;
}

.table-head,
.project-row {
  display: grid;
  grid-template-columns: minmax(190px, 1.45fr) 86px 100px 80px minmax(140px, 1.1fr) 76px;
  gap: 10px;
  align-items: center;
  padding: 0 18px;
}

.table-head {
  min-height: 32px;
  color: #94a3b8;
  border-bottom: 1px solid #f1f5f9;
  background: #fcfdff;
  font-size: 11px;
  font-weight: 600;
}

.actions-head {
  text-align: right;
}

.project-row {
  position: relative;
  width: 100%;
  min-height: 68px;
  border: 0;
  border-bottom: 1px solid #f1f5f9;
  color: #40506a;
  background: #fff;
  text-align: left;
  transition: transform 0.22s cubic-bezier(0.2, 0.8, 0.2, 1), background 0.2s ease, box-shadow 0.22s ease;
}

.project-row:hover {
  z-index: 1;
  background: #f8fafc;
  transform: translateY(-1px);
  box-shadow: 0 6px 14px rgba(15, 23, 42, 0.07);
}

.project-row:active {
  transform: translateY(0);
}

.project-row.selected {
  background: #eff6ff;
}

.project-row.selected:hover {
  background: #e8f1ff;
}

.project-row:last-child {
  border-bottom: 0;
}

.project-identity {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.repo-icon {
  width: 32px;
  height: 32px;
  display: grid;
  place-items: center;
  flex: 0 0 32px;
  border-radius: 7px;
  color: #59708e;
  background: #f8fafc;
  transition: transform 0.24s cubic-bezier(0.34, 1.56, 0.64, 1), color 0.2s ease, background 0.2s ease;
}

.project-row:hover .repo-icon {
  transform: scale(1.1);
  color: #2563eb;
  background: #eef5ff;
}

.identity-copy {
  min-width: 0;
}

.identity-copy strong {
  display: block;
  overflow: hidden;
  color: #172033;
  font-size: 13px;
  font-weight: 650;
  text-overflow: ellipsis;
  white-space: nowrap;
  transition: color 0.2s ease;
}

.project-row:hover .identity-copy strong {
  color: #1d4ed8;
}

.identity-copy small {
  display: block;
  margin-top: 3px;
  overflow: hidden;
  color: #94a3b8;
  font-size: 11px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.language,
.scan-time {
  color: #475569;
  font-size: 12px;
}

.scan-time {
  color: #64748b;
}

.scan-time small {
  display: block;
  margin-top: 2px;
  color: #94a3b8;
  font-size: 11px;
}

.risk-list {
  display: flex;
  gap: 8px;
  color: #64748b;
  font-size: 11px;
}

.risk-list span {
  display: inline-flex;
  align-items: center;
  gap: 3px;
}

.risk-list i {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}

.critical i {
  background: #b42318;
}

.high i {
  background: #d14343;
}

.medium i {
  background: #d97706;
}

.low i {
  background: #16a34a;
}

.agent-activity {
  display: flex;
  align-items: center;
  gap: 7px;
  min-width: 0;
}

.agent-activity > :deep(.ui-icon) {
  color: #2563eb;
}

.agent-activity > span {
  min-width: 0;
}

.agent-activity strong {
  display: block;
  overflow: hidden;
  color: #475569;
  font-size: 12px;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.agent-activity small {
  display: flex;
  align-items: center;
  gap: 5px;
  margin-top: 3px;
  color: #64748b;
  font-size: 11px;
}

.agent-activity small i {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #cbd5e1;
}

.agent-activity small.running {
  color: #2563eb;
}

.agent-activity small.running i {
  background: #2563eb;
  box-shadow: 0 0 0 3px #dbeafe;
  animation: pulse 1.5s ease-in-out infinite;
}

.agent-activity small.done {
  color: #16834d;
}

.agent-activity small.done i {
  background: #16a34a;
}

.row-actions {
  display: flex;
  justify-content: flex-end;
  gap: 6px;
}

.icon-button {
  width: 29px;
  height: 29px;
  display: grid;
  place-items: center;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  color: #64748b;
  background: #fff;
  transition: transform 0.2s ease, border-color 0.2s ease, color 0.2s ease, background 0.2s ease, box-shadow 0.2s ease;
}

.icon-button:hover {
  transform: translateY(-2px) scale(1.06);
  border-color: #93b4f7;
  color: #2563eb;
  background: #eff6ff;
  box-shadow: 0 3px 8px rgba(37, 99, 235, 0.18);
}

.icon-button:active {
  transform: translateY(0) scale(1);
}

.icon-button.primary {
  border-color: #bfdbfe;
  color: #2563eb;
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

@media (max-width: 1120px) {
  .table-head,
  .project-row {
    grid-template-columns: minmax(175px, 1.35fr) 74px 86px 70px minmax(120px, 1fr) 65px;
    gap: 8px;
  }
}

@media (max-width: 720px) {
  .project-table {
    height: auto;
    max-height: 420px;
  }
  .table-scroll {
    overflow-x: auto;
  }
  .table-head,
  .project-row {
    min-width: 760px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .project-row,
  .repo-icon,
  .identity-copy strong,
  .icon-button {
    transition: none;
  }
  .project-row:hover,
  .icon-button:hover,
  .project-row:hover .repo-icon {
    transform: none;
  }
  .agent-activity small.running i {
    animation: none;
  }
}
</style>
