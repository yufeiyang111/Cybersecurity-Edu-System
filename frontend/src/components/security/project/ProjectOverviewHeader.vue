<template>
  <section class="project-overview-card" aria-label="项目摘要">
    <div class="project-overview-card__main">
      <div class="project-title-row">
        <span class="project-mark">
          <el-icon><Collection /></el-icon>
        </span>
        <div class="project-title-copy">
          <span class="project-kicker">PROJECT / {{ projectCode }}</span>
          <h1 class="project-title">
            {{ project.name }}
            <span class="status-chip" :class="`status-chip--${scanState.kind}`">
              <i class="status-chip__dot" />
              {{ scanState.label }}
            </span>
          </h1>
        </div>
      </div>

      <div v-if="selectedTask" class="project-meta-row">
        <span class="meta-item">
          <el-icon><Collection /></el-icon>
          快照 #{{ selectedTask.snapshot_id }}
        </span>
        <span class="meta-item meta-item--language" :title="languageLabel">
          <el-icon><Document /></el-icon>
          {{ languageLabel }}
        </span>
        <span class="meta-item">
          <el-icon><Clock /></el-icon>
          {{ recentTaskLabel }}
        </span>
      </div>
      <p v-else class="project-empty-meta">暂无扫描记录</p>
    </div>

    <div class="project-health" :class="`project-health--${healthState.kind}`">
      <div class="project-health__head">
        <span>当前安全状态</span>
        <strong>{{ healthState.label }}</strong>
      </div>
      <div class="project-health__score">
        {{ scoreText }}
        <small v-if="scoreText !== '-'">/ 100</small>
      </div>
      <p>{{ selectedTask ? '当前选中任务' : '等待扫描任务' }}</p>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { Clock, Collection, Document } from '@element-plus/icons-vue'

const props = defineProps({
  project: { type: Object, required: true },
  scanState: { type: Object, required: true },
  selectedTask: { type: Object, default: null },
  languageLabel: { type: String, default: '未识别' },
  recentTaskLabel: { type: String, default: '' },
  avgRiskScore: { type: Number, default: null }
})

const projectCode = computed(() => String(props.project.id).padStart(2, '0'))
const scoreText = computed(() => (
  props.avgRiskScore === null ? '-' : Math.round(props.avgRiskScore)
))
const healthState = computed(() => {
  if (props.avgRiskScore === null) return { kind: 'none', label: '待扫描' }
  if (props.avgRiskScore >= 60) return { kind: 'warning', label: '需要关注' }
  return { kind: 'ok', label: '运行正常' }
})
</script>

<style scoped lang="scss">
.project-overview-card {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 220px;
  gap: 24px;
  padding: 20px 22px;
  border: 1px solid #dfe6ef;
  border-radius: 10px;
  background: #ffffff;
  box-shadow: 0 3px 12px rgba(21, 40, 75, 0.045);
  transition: border-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease;
}

.project-overview-card:hover {
  border-color: #c4d3e4;
  box-shadow: 0 10px 24px rgba(21, 40, 75, 0.09);
  transform: translateY(-1px);
}

.project-overview-card__main {
  min-width: 0;
}

.project-title-row {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.project-mark {
  display: inline-flex;
  width: 42px;
  height: 42px;
  flex: 0 0 42px;
  align-items: center;
  justify-content: center;
  border: 1px solid #c9daf8;
  border-radius: 10px;
  color: #2563eb;
  background: #eff6ff;
}

.project-mark .el-icon {
  font-size: 20px;
}

.project-title-copy {
  min-width: 0;
}

.project-kicker {
  display: block;
  margin-bottom: 2px;
  color: #94a3b8;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.12em;
}

.project-title {
  display: flex;
  align-items: center;
  gap: 9px;
  flex-wrap: wrap;
  margin: 0;
  color: #142238;
  font-size: 20px;
  font-weight: 700;
  letter-spacing: -0.02em;
  line-height: 1.25;
}

.status-chip {
  display: inline-flex;
  min-height: 23px;
  align-items: center;
  gap: 5px;
  padding: 0 8px;
  border: 1px solid #b7e4ca;
  border-radius: 5px;
  color: #16834d;
  background: #ecfdf3;
  font-size: 11px;
  font-weight: 650;
  letter-spacing: 0;
}

.status-chip--run {
  border-color: #bfdbfe;
  color: #2563eb;
  background: #eff6ff;
}

.status-chip--none {
  border-color: #dce4ee;
  color: #7e8da3;
  background: #f8fafc;
}

.status-chip__dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: currentColor;
}

.status-chip--run .status-chip__dot {
  animation: status-breathe 1.5s ease-in-out infinite;
}

.project-meta-row {
  display: flex;
  align-items: center;
  gap: 7px;
  flex-wrap: wrap;
  margin: 15px 0 0 54px;
}

.meta-item {
  display: inline-flex;
  min-height: 24px;
  max-width: 100%;
  align-items: center;
  gap: 5px;
  padding: 2px 8px;
  overflow: hidden;
  border: 1px solid #e0e7ef;
  border-radius: 5px;
  color: #52627a;
  background: #f8fafc;
  font-size: 11.5px;
  white-space: nowrap;
}

.meta-item .el-icon {
  flex: 0 0 auto;
  color: #7e8da3;
}

.meta-item--language {
  text-overflow: ellipsis;
}

.project-empty-meta {
  margin: 15px 0 0 54px;
  color: #7e8da3;
  font-size: 12px;
}

.project-health {
  align-self: stretch;
  padding-left: 20px;
  border-left: 1px solid #edf1f5;
}

.project-health__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  color: #7e8da3;
  font-size: 11.5px;
}

.project-health__head strong {
  color: #16834d;
  font-size: 11.5px;
  font-weight: 700;
}

.project-health--warning .project-health__head strong {
  color: #c8751b;
}

.project-health--none .project-health__head strong {
  color: #7e8da3;
}

.project-health__score {
  margin-top: 12px;
  color: #142238;
  font-size: 32px;
  font-weight: 760;
  letter-spacing: -0.04em;
  line-height: 1;
}

.project-health__score small {
  margin-left: 3px;
  color: #7e8da3;
  font-size: 12px;
  font-weight: 500;
  letter-spacing: 0;
}

.project-health p {
  margin: 8px 0 0;
  color: #7e8da3;
  font-size: 11px;
}

@keyframes status-breathe {
  0%,
  100% {
    opacity: 1;
  }

  50% {
    opacity: 0.35;
  }
}

@media (max-width: 760px) {
  .project-overview-card {
    grid-template-columns: 1fr;
    gap: 16px;
    padding: 17px;
  }

  .project-health {
    padding: 15px 0 0;
    border-top: 1px solid #edf1f5;
    border-left: 0;
  }

  .project-meta-row,
  .project-empty-meta {
    margin-left: 0;
  }
}
</style>
