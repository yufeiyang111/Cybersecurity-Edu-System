<template>
  <section class="sca-finding-list">
    <div class="section-heading">
      <div>
        <p class="section-eyebrow">PERSISTED SCA FINDINGS</p>
        <h3>依赖风险</h3>
        <p>仅来自当前扫描任务已持久化的 SCA Finding，可回到主 Finding 区进行人工研判。</p>
      </div>
      <el-tag type="danger" effect="plain">{{ findings.length }} 条</el-tag>
    </div>

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
        </div>
        <p v-if="finding.evidence?.[0]?.content" class="evidence-preview">脱敏证据：{{ finding.evidence[0].content }}</p>
        <el-button text type="primary" size="small" @click="emit('select-finding', finding.id)">定位主 Finding</el-button>
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
.sca-finding-list { padding: 20px; border: 1px solid #d9e2ec; border-radius: 14px; background: #fff; }
.section-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 16px; }
.section-eyebrow { margin: 0 0 6px; color: #0e9384; font-size: 11px; font-weight: 700; letter-spacing: .09em; }
h3 { margin: 0; color: #102a43; font-size: 17px; }
.section-heading > div > p:last-child { margin: 8px 0 0; color: #627d98; font-size: 13px; line-height: 1.6; }
.sca-findings { display: grid; gap: 12px; }
.sca-finding-item { padding: 16px; border: 1px solid #e5eaf0; border-radius: 10px; background: #fcfdff; }
.sca-finding-item__header, .sca-finding-item__meta { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
.sca-finding-item__header code, .sca-finding-item__meta code { padding: 3px 6px; border-radius: 4px; background: #eef3f8; color: #243b53; font-size: 12px; overflow-wrap: anywhere; }
.sca-finding-item__header span, .sca-finding-item__meta span { color: #627d98; font-size: 12px; }
.sca-finding-item > p { margin: 12px 0; color: #334e68; line-height: 1.6; }
.evidence-preview { padding: 10px; border-radius: 8px; background: #fff8e6; color: #7c5d14 !important; font-size: 12px; overflow-wrap: anywhere; }
</style>
