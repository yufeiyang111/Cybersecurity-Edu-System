<template>
  <article class="sca-status-card" :class="`sca-status-card--${status.kind}`">
    <div class="sca-status-card__header">
      <h3>{{ status.title }}</h3>
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
.sca-status-card { padding: 12px 14px; border: 1px solid #e2e7ee; border-radius: 6px; background: #f8fbfc; }
.sca-status-card--risk { border-color: #f3c2c2; background: #fff7f7; }
.sca-status-card--warning { border-color: #eed9a4; background: #fffaf0; }
.sca-status-card--clear { border-color: #c3e6d4; background: #f1fcf7; }
.sca-status-card__header { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
h3 { margin: 0; color: #1f2d3d; font-size: 14px; }
.sca-status-card > p { margin: 8px 0 0; color: #52627a; line-height: 1.6; font-size: 13px; }
.sca-status-card__count { font-weight: 700; color: #b42318 !important; }
.sca-warning-list { margin: 10px 0 0; padding: 8px 10px 8px 26px; border-radius: 6px; background: rgba(255, 255, 255, .72); color: #7c5d14; font-size: 12.5px; line-height: 1.6; }
</style>
