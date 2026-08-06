<template>
  <section class="summary-band"><div v-for="item in items" :key="item.label" class="summary-item"><div class="summary-label"><span class="summary-icon"><BaseIcon :name="item.icon" :size="17" /></span>{{ item.label }}</div><div class="summary-value">{{ item.value }}</div><div class="summary-note">{{ item.note }}</div></div></section>
</template>

<script setup>
import { computed } from 'vue'
import { BaseIcon } from '@/components/ui'
import { formatInteger } from '@/features/security/llm/format'

const props = defineProps({ summary: { type: Object, default: () => ({}) } })
const items = computed(() => [{ icon: 'chart', label: '总数', value: formatInteger(props.summary.total_calls), note: '统计计数' }, { icon: 'layers', label: '缓存命中率', value: `${Number(props.summary.cache_hit_rate || 0).toFixed(1)}%`, note: '缓存 Token ÷ 输入 Token' }, { icon: 'coins', label: '总 TOKEN 数', value: formatInteger(props.summary.total_tokens), note: '统计 Token 数' }, { icon: 'activity', label: '平均 RPM', value: Number(props.summary.rpm || 0).toFixed(2), note: '每分钟请求数' }, { icon: 'zap', label: '平均 TPM', value: formatInteger(props.summary.tpm), note: '每分钟 Token 数' }])
</script>

<style scoped lang="scss">
.summary-band{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));margin-bottom:20px;border:1px solid #e2e8f0;border-radius:8px;overflow:hidden;background:#fff}.summary-item{min-height:126px;padding:18px 20px;border-right:1px solid #e2e8f0;transition:background .35s ease,box-shadow .35s ease,transform .35s ease}.summary-item:last-child{border-right:0}.summary-item:hover{background:#f8fafc;box-shadow:inset 0 2px 0 0 #2563eb;transform:translateY(-2px)}.summary-label{display:flex;align-items:center;gap:8px;color:#475569;font-size:12px}.summary-icon{width:30px;height:30px;display:grid;place-items:center;border-radius:6px;background:#dbeafe;color:#2563eb;transition:transform .35s ease,background .35s ease}.summary-item:hover .summary-icon{transform:scale(1.08);background:#bfdbfe}.summary-value{margin-top:14px;color:#0f172a;font-size:22px;line-height:1;font-weight:700;transition:color .35s ease}.summary-item:hover .summary-value{color:#2563eb}.summary-note{margin-top:9px;color:#94a3b8;font-size:11px}@media(max-width:1120px){.summary-band{grid-template-columns:repeat(3,1fr)}.summary-item:nth-child(3){border-right:0}.summary-item:nth-child(n+4){border-top:1px solid #e2e8f0}}@media(max-width:640px){.summary-band{grid-template-columns:1fr 1fr}.summary-item{padding:15px}.summary-item:nth-child(2){border-right:0}.summary-item:nth-child(n+3){border-top:1px solid #e2e8f0}}
</style>
