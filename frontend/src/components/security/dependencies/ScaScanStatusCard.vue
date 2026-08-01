<template>
  <article class="sca-status-card" :class="`sca-status-card--${status.kind}`">
    <div class="sca-status-card__header">
      <div>
        <p class="sca-status-card__eyebrow">SOFTWARE COMPOSITION ANALYSIS</p>
        <h3>{{ status.title }}</h3>
      </div>
      <el-tag :type="tagType" effect="light">{{ tagLabel }}</el-tag>
    </div>
    <p>{{ status.description }}</p>
    <p v-if="status.kind === 'risk'" class="sca-status-card__count">{{ status.findingCount }} 条已持久化风险发现</p>
    <ul v-if="status.warnings?.length" class="sca-warning-list" aria-label="SCA 扫描告警">
      <li v-for="warning in status.warnings" :key="warning">{{ warning }}</li>
    </ul>
  </article>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  status: {
    type: Object,
    required: true
  }
})

const tagType = computed(() => ({
  risk: 'danger',
  warning: 'warning',
  clear: 'success',
  'not-enabled': 'info',
  unknown: 'info'
}[props.status.kind] || 'info'))

const tagLabel = computed(() => ({
  risk: '需处理',
  warning: '需复核',
  clear: '已完成查询',
  'not-enabled': '未启用',
  unknown: '待确认'
}[props.status.kind] || '待确认'))
</script>

<style scoped lang="scss">
.sca-status-card { padding: 20px; border: 1px solid #d9e2ec; border-radius: 14px; background: #f8fbfc; }
.sca-status-card--risk { border-color: #fecaca; background: #fff7f7; }
.sca-status-card--warning { border-color: #f8d78d; background: #fffaf0; }
.sca-status-card--clear { border-color: #b7ead7; background: #f1fcf7; }
.sca-status-card__header { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
.sca-status-card__eyebrow { margin: 0 0 6px; color: #627d98; font-size: 11px; font-weight: 700; letter-spacing: .09em; }
h3 { margin: 0; color: #102a43; font-size: 17px; }
.sca-status-card > p { margin: 10px 0 0; color: #486581; line-height: 1.65; }
.sca-status-card__count { font-weight: 700; color: #b42318 !important; }
.sca-warning-list { margin: 14px 0 0; padding: 12px 12px 12px 30px; border-radius: 8px; background: rgba(255, 255, 255, .72); color: #7c5d14; font-size: 13px; line-height: 1.6; }
</style>
