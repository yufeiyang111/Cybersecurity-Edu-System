<template>
  <section v-if="citations.length" class="citation-list">
    <div class="citation-list__header">
      <strong>RAG 引用</strong>
      <span>{{ citations.length }} 条服务端返回的知识引用</span>
    </div>
    <article v-for="(citation, index) in citations" :key="citation.citation_id || index" class="citation-item">
      <div>
        <code>{{ citation.citation_id }}</code>
        <span>{{ citation.source_name }} · {{ citation.title }} · {{ citation.version || '未标注版本' }}</span>
      </div>
      <div v-if="hasGovernance(citation)" class="citation-governance">
        <span class="trust-badge" :class="trustToneClass(citation.trust_score)">
          可信度 {{ trustPercent(citation.trust_score) }}
        </span>
        <el-tag
          v-for="flag in citation.injection_flags || []"
          :key="flag"
          type="danger"
          size="small"
          effect="dark"
          class="flag-tag"
        >{{ injectionFlagLabel(flag) }}</el-tag>
      </div>
      <p>{{ citation.snippet }}</p>
    </article>
  </section>
</template>

<script setup>
import { injectionFlagLabel } from '@/features/security/warningCodes'

const props = defineProps({
  citations: { type: Array, default: () => [] }
})

const hasGovernance = (citation) =>
  citation.trust_score !== undefined || (citation.injection_flags && citation.injection_flags.length)

const trustPercent = (score) =>
  typeof score === 'number' ? `${Math.round(score * 100)}%` : '服务端未提供'

const trustToneClass = (score) => {
  if (typeof score !== 'number') return 'trust-neutral'
  if (score >= 0.8) return 'trust-high'
  if (score >= 0.6) return 'trust-mid'
  return 'trust-low'
}
</script>

<style scoped lang="scss">
.citation-list { margin-top: 10px; padding: 10px 12px; border-radius: 6px; background: #f4f8f6; border: 1px solid #d7eee4; max-height: 320px; overflow-y: auto; }
.citation-list::-webkit-scrollbar { width: 8px; }
.citation-list::-webkit-scrollbar-thumb { background: #c2ccd9; border-radius: 4px; }
.citation-list::-webkit-scrollbar-track { background: transparent; }
.citation-list__header { display: flex; justify-content: space-between; gap: 10px; flex-wrap: wrap; }
.citation-list strong { color: #155c48; font-size: 12.5px; }
.citation-list__header span { color: #6a7890; font-size: 12px; }
.citation-item { padding: 8px 0; border-top: 1px solid #dfe9e4; }
.citation-item:first-of-type { border-top: 0; padding-top: 8px; }
.citation-item div { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
.citation-item code { color: #087f5b; font-size: 11.5px; }
.citation-item span, .citation-item p { color: #52627a; font-size: 12px; }
.citation-item p { margin: 6px 0 0; white-space: pre-wrap; line-height: 1.6; }
.citation-governance { margin-top: 6px; }
.trust-badge {
  display: inline-flex; align-items: center;
  padding: 2px 8px; border-radius: 4px;
  font-size: 12px; font-weight: 600;
}
.trust-high { color: #087f5b; background: #e6f7f0; }
.trust-mid { color: #b7791f; background: #fdf4e3; }
.trust-low { color: #c53030; background: #fdeaea; }
.trust-neutral { color: #627d98; background: #eef2f6; }
.flag-tag { margin-left: 6px; }
</style>
