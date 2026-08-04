<template>
  <article class="project-card" :class="{ 'project-card--expanded': expanded }" @click="$emit('toggle')">
    <div class="pc-top">
      <div class="pc-info">
        <span class="lang-icon" :style="{ background: lang.color }">{{ lang.code }}</span>
        <div class="pc-text">
          <div class="nm">{{ project.name }}</div>
          <div class="ds">{{ project.description || '尚未填写项目说明' }}</div>
        </div>
      </div>
      <div class="pc-state" :class="`st-${state.kind}`">
        <span class="dot" :class="`dot--${state.kind}`" />
        <span>{{ state.label }}</span>
      </div>
    </div>

    <div class="pc-divider" />

    <div class="pc-vulns">
      <span class="vuln-item"><span class="dot v-crit" />严重 <b>{{ project.vulns?.critical ?? 0 }}</b></span>
      <span class="vuln-item"><span class="dot v-high" />高危 <b>{{ project.vulns?.high ?? 0 }}</b></span>
      <span class="vuln-item"><span class="dot v-med" />中危 <b>{{ project.vulns?.medium ?? 0 }}</b></span>
      <span class="vuln-item"><span class="dot v-low" />低危 <b>{{ project.vulns?.low ?? 0 }}</b></span>
    </div>

    <div class="pc-bottom">
      <div class="pc-meta">
        <span>上次扫描 {{ lastScanText }}</span>
        <span>{{ project.files ?? 0 }} 个文件</span>
        <span>共 {{ project.scan_count ?? 0 }} 次扫描</span>
      </div>
      <div class="pc-ops" @click.stop>
        <el-button size="small" @click="$emit('view')">查看任务</el-button>
        <el-button size="small" :icon="Link" @click="$emit('github')">GitHub 导入</el-button>
        <el-button size="small" type="primary" :icon="Upload" @click="$emit('upload')">上传 ZIP 扫描</el-button>
      </div>
    </div>
  </article>
</template>

<script setup>
import { computed } from 'vue'
import { Link, Upload } from '@element-plus/icons-vue'
import { languageMeta } from '@/features/security/languageMeta'

const props = defineProps({
  project: { type: Object, required: true },
  expanded: { type: Boolean, default: false }
})

defineEmits(['toggle', 'view', 'github', 'upload'])

const RUNNING_STATUSES = new Set(['created', 'validating', 'snapshotting', 'scanning'])

const lang = computed(() => languageMeta(props.project.language))

const state = computed(() => {
  const status = props.project.scan_status
  if (!status) return { kind: 'none', label: '未扫描' }
  if (RUNNING_STATUSES.has(status)) return { kind: 'running', label: '扫描中' }
  if (status === 'failed') return { kind: 'fail', label: '扫描失败' }
  if (status === 'canceled') return { kind: 'none', label: '已取消' }
  return { kind: 'done', label: '扫描完成' }
})

const lastScanText = computed(() => {
  const value = props.project.last_scan_at
  if (!value) return '—'
  const date = new Date(value)
  const pad = (n) => String(n).padStart(2, '0')
  return `${date.getFullYear()}/${pad(date.getMonth() + 1)}/${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
})
</script>

<style scoped lang="scss">
.project-card {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 16px 18px;
  cursor: pointer;
  transition: box-shadow 0.2s ease, transform 0.2s ease, border-color 0.2s ease;

  &:hover {
    box-shadow: 0 6px 18px rgba(15, 23, 42, 0.08);
    transform: translateY(-1px);
    border-color: #bfdbfe;
  }

  &--expanded {
    border-color: #93c5fd;
    box-shadow: 0 6px 18px rgba(37, 99, 235, 0.1);
  }
}

.pc-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.pc-info {
  display: flex;
  align-items: center;
  gap: 13px;
  min-width: 0;

  .lang-icon {
    width: 44px;
    height: 44px;
    border-radius: 8px;
    color: #fff;
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 0.3px;
  }

  .nm {
    font-size: 15px;
    font-weight: 600;
    color: #0f172a;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .ds {
    margin-top: 2px;
    font-size: 12.5px;
    color: #475569;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    max-width: 480px;
  }
}

.pc-state {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 13px;
  white-space: nowrap;
  padding-top: 2px;

  .dot {
    width: 9px;
    height: 9px;
    border-radius: 50%;

    &--done { background: #16a34a; }
    &--running { background: #2563eb; animation: breathe 1.6s ease-in-out infinite; }
    &--fail { background: #dc2626; }
    &--none { background: #cbd5e1; }
  }
}

.st-done { color: #15803d; }
.st-running { color: #2563eb; }
.st-fail { color: #dc2626; }
.st-none { color: #94a3b8; }

@keyframes breathe {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}

.pc-divider {
  height: 1px;
  background: #e2e8f0;
  margin: 13px 0;
}

.pc-vulns {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 28px;

  .vuln-item {
    display: flex;
    align-items: center;
    gap: 7px;
    font-size: 12.5px;
    color: #475569;

    .dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
    }

    b {
      font-size: 13px;
      font-variant-numeric: tabular-nums;
      color: #0f172a;
      font-weight: 600;
    }
  }
}

.v-crit { background: #dc2626; }
.v-high { background: #ea580c; }
.v-med { background: #ca8a04; }
.v-low { background: #16a34a; }

.pc-bottom {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 13px;
  flex-wrap: wrap;
}

.pc-meta {
  display: flex;
  gap: 16px;
  color: #94a3b8;
  font-size: 12.5px;

  span {
    white-space: nowrap;
  }
}

.pc-ops {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

@media (max-width: 720px) {
  .pc-ops {
    width: 100%;
  }
}
</style>
