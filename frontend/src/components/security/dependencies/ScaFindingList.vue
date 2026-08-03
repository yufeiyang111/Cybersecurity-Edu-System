<template>
  <section class="sca-finding-list">
    <el-skeleton v-if="loading" :rows="3" animated />
    <el-empty v-else-if="findings.length === 0" description="当前任务没有可展示的 SCA Finding。" />
    <div v-else class="sca-findings">
      <article v-for="finding in findings" :key="finding.id" class="sca-finding-item">
        <div class="sca-finding-item__header">
          <FindingSeverityTag :severity="finding.severity" />
          <code>{{ finding.rule_id }}</code>
          <span v-if="finding.cve_id">{{ finding.cve_id }}</span>
        </div>
        <p>{{ finding.message }}</p>
        <div class="sca-finding-item__meta">
          <code>{{ finding.file_path }}:{{ finding.start_line }}</code>
          <span>置信度：{{ formatConfidence(finding.confidence) }}</span>
          <el-button text type="primary" size="small" @click="emit('select-finding', finding.id)">定位主 Finding</el-button>
        </div>
      </article>
    </div>
  </section>
</template>

<script setup>
import FindingSeverityTag from '@/components/security/FindingSeverityTag.vue'

const emit = defineEmits(['select-finding'])

defineProps({
  findings: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false }
})

const formatConfidence = (confidence) => {
  if (typeof confidence !== 'number') return '服务端未提供'
  return `${Math.round(confidence * 100)}%`
}
</script>

<style scoped lang="scss">
.sca-findings { display: grid; gap: 8px; }
.sca-finding-item { padding: 10px 12px; border: 1px solid #e5eaf0; border-radius: 6px; background: #fcfdff; }
.sca-finding-item__header, .sca-finding-item__meta { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
.sca-finding-item__header code, .sca-finding-item__meta code { padding: 2px 6px; border-radius: 4px; background: #f1f4f8; color: #37465c; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 11.5px; overflow-wrap: anywhere; }
.sca-finding-item__header span, .sca-finding-item__meta span { color: #8494a8; font-size: 12px; }
.sca-finding-item > p { margin: 8px 0; color: #37465c; font-size: 13px; line-height: 1.6; }
</style>
