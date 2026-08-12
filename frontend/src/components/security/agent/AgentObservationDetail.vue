<template>
  <el-drawer
    :model-value="visible"
    size="520px"
    :title="observation?.title || '观察结论详情'"
    @close="$emit('close')"
  >
    <div v-if="loading" class="obs-detail__empty">加载中…</div>
    <div v-else-if="observation" class="obs-detail">
      <div class="obs-detail__head">
        <el-tag :type="statusTagType(observation.status)" size="small">
          {{ statusLabel(observation.status) }}
        </el-tag>
        <span class="obs-detail__confidence">{{ confidenceLabel(observation.confidence) }}</span>
        <span v-if="observation.cwe_id" class="obs-detail__cwe">{{ observation.cwe_id }}</span>
      </div>

      <p class="obs-detail__summary">{{ observation.summary }}</p>

      <div v-if="reviewable" class="obs-detail__review">
        <el-input
          v-model="reviewComment"
          size="small"
          placeholder="审核意见（可选）"
          class="obs-detail__review-comment"
        />
        <el-button
          size="small"
          type="success"
          plain
          :loading="reviewing"
          @click="$emit('review', observation, 'confirmed', reviewComment)"
        >
          确认
        </el-button>
        <el-button
          size="small"
          type="warning"
          plain
          :loading="reviewing"
          @click="$emit('review', observation, 'needs_more_evidence', reviewComment)"
        >
          待补证据
        </el-button>
        <el-button
          size="small"
          type="danger"
          plain
          :loading="reviewing"
          @click="$emit('review', observation, 'rejected', reviewComment)"
        >
          驳回
        </el-button>
      </div>

      <div v-if="observation.status === 'confirmed'" class="obs-detail__remediation">
        <el-button
          size="small"
          type="primary"
          plain
          :loading="generatingDiff"
          @click="$emit('generate-diff', observation)"
        >
          生成修复 Diff
        </el-button>
      </div>

      <div v-if="remediationDiff" class="obs-detail__diff">
        <div class="obs-detail__diff-head">
          <span class="obs-detail__label">修复建议（只读，不自动应用）</span>
          <el-button size="small" text type="primary" @click="copyDiff">复制</el-button>
        </div>
        <pre class="obs-detail__diff-pre">{{ remediationDiff }}</pre>
      </div>

      <el-alert
        v-if="injectionCount > 0"
        title="部分检索知识被注入检测剔除，未进入上下文"
        type="warning"
        :closable="false"
        show-icon
      />

      <div v-if="observation.detail?.impact" class="obs-detail__block">
        <span class="obs-detail__label">风险影响</span>
        <p class="obs-detail__text">{{ observation.detail.impact }}</p>
      </div>
      <div v-if="observation.detail?.evidence_chain?.length" class="obs-detail__block">
        <span class="obs-detail__label">证据链</span>
        <ol class="obs-detail__chain">
          <li v-for="(item, index) in observation.detail.evidence_chain" :key="index">
            {{ item }}
          </li>
        </ol>
      </div>

      <div v-if="(observation.locations || []).length" class="obs-detail__block">
        <span class="obs-detail__label">受影响位置</span>
        <ul class="obs-detail__locations">
          <li v-for="location in observation.locations" :key="location.id">
            <code>{{ location.file_path }}</code>
            第 {{ location.start_line ?? '?' }}-{{ location.end_line ?? location.start_line ?? '?' }} 行
            <el-tag size="small" type="info">{{ roleLabel(location.role) }}</el-tag>
          </li>
        </ul>
      </div>

      <div v-if="(observation.citations || []).length" class="obs-detail__block">
        <span class="obs-detail__label">知识引用</span>
        <ul class="obs-detail__citations">
          <li v-for="citation in observation.citations" :key="citation.id">
            <span class="obs-detail__cite-title">{{ citation.document_title }}</span>
            <span v-if="citation.trust_score != null" class="obs-detail__cite-score">
              信任 {{ citation.trust_score }}
            </span>
            <span v-if="citation.injection_flags?.length" class="obs-detail__cite-flag">
              注入标记
            </span>
            <span class="obs-detail__cite-digest">{{ (citation.content_digest || '').slice(0, 12) }}…</span>
            <p v-if="citation.quote_preview" class="obs-detail__cite-quote">
              {{ citation.quote_preview }}
            </p>
          </li>
        </ul>
      </div>

      <div v-if="(observation.proof_gaps || []).length" class="obs-detail__block">
        <span class="obs-detail__label">证据缺口</span>
        <ul class="obs-detail__gaps">
          <li v-for="(gap, index) in observation.proof_gaps" :key="index">{{ gap }}</li>
        </ul>
      </div>
    </div>
  </el-drawer>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { ElMessage } from '@/features/security/feedback'

const props = defineProps({
  visible: { type: Boolean, default: false },
  observation: { type: Object, default: null },
  loading: { type: Boolean, default: false },
  reviewing: { type: Boolean, default: false },
  generatingDiff: { type: Boolean, default: false }
})

const emit = defineEmits(['close', 'review', 'generate-diff'])

const reviewComment = ref('')
const remediationDiff = ref('')

watch(
  () => props.observation?.id,
  () => {
    reviewComment.value = ''
    remediationDiff.value = props.observation?.detail?.remediation_diff?.diff || ''
  }
)

const reviewable = computed(() => {
  const status = props.observation?.status
  return status === 'unverified' || status === 'needs_more_evidence'
})

async function copyDiff() {
  try {
    await navigator.clipboard.writeText(remediationDiff.value)
    ElMessage.success('Diff 已复制')
  } catch (error) {
    ElMessage.error('复制失败，请手动选择复制')
  }
}

const STATUS_LABELS = {
  unverified: '未验证',
  confirmed: '已确认',
  rejected: '已驳回',
  needs_more_evidence: '待补证据'
}

const CONFIDENCE_LABELS = {
  low: '低置信',
  medium: '中置信',
  high: '高置信'
}

const ROLE_LABELS = {
  sink: '危险汇点',
  source: '输入源',
  entry: '入口',
  evidence: '证据'
}

const injectionCount = computed(
  () =>
    (props.observation?.citations || []).filter(
      (citation) => citation.injection_flags && citation.injection_flags.length
    ).length
)

function statusLabel(status) {
  return STATUS_LABELS[status] || status
}

function statusTagType(status) {
  if (status === 'confirmed') return 'success'
  if (status === 'rejected') return 'info'
  if (status === 'needs_more_evidence') return 'warning'
  return 'primary'
}

function confidenceLabel(confidence) {
  return CONFIDENCE_LABELS[confidence] || confidence
}

function roleLabel(role) {
  return ROLE_LABELS[role] || role
}
</script>

<style scoped lang="scss">
.obs-detail__empty {
  color: #8494a8;
  font-size: 13px;
  padding: 20px 0;
  text-align: center;
}

.obs-detail__head {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.obs-detail__confidence {
  font-size: 12.5px;
  color: #52627a;
}

.obs-detail__cwe {
  font-size: 11.5px;
  color: #9aa6ba;
  background: #f0f2f6;
  border-radius: 4px;
  padding: 1px 6px;
}

.obs-detail__summary {
  margin: 12px 0;
  font-size: 13px;
  line-height: 1.7;
  color: #1f2d3d;
}

.obs-detail__block {
  margin-top: 14px;
}

.obs-detail__label {
  display: block;
  font-size: 12.5px;
  font-weight: 600;
  color: #6a7890;
  margin-bottom: 6px;
}

.obs-detail__text {
  margin: 0;
  font-size: 12.5px;
  line-height: 1.6;
  color: #52627a;
}

.obs-detail__chain {
  margin: 0;
  padding-left: 18px;
  font-size: 12.5px;
  line-height: 1.7;
  color: #52627a;
}

.obs-detail__locations,
.obs-detail__citations,
.obs-detail__gaps {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.obs-detail__locations li,
.obs-detail__citations li {
  font-size: 12.5px;
  color: #52627a;
  line-height: 1.6;
  border: 1px solid #eef1f6;
  border-radius: 6px;
  padding: 6px 8px;
  background: #fbfcfe;
}

.obs-detail__locations code {
  background: #eef2f8;
  border-radius: 4px;
  padding: 1px 5px;
  font-size: 12px;
  color: #1f2d3d;
}

.obs-detail__cite-title {
  font-weight: 600;
  color: #1f2d3d;
}

.obs-detail__cite-score {
  margin-left: 6px;
  color: #2563eb;
}

.obs-detail__cite-flag {
  margin-left: 6px;
  color: #b45309;
  font-weight: 600;
}

.obs-detail__cite-digest {
  margin-left: 6px;
  color: #a0aaba;
  font-size: 11.5px;
}

.obs-detail__cite-quote {
  margin: 4px 0 0;
  font-size: 12px;
  color: #6a7890;
  line-height: 1.5;
}

.obs-detail__gaps li {
  font-size: 12.5px;
  color: #b45309;
  border: 1px solid #fef3c7;
  border-radius: 6px;
  padding: 6px 8px;
  background: #fffbeb;
}

.obs-detail__review {
  display: flex;
  gap: 6px;
  align-items: center;
  margin: 10px 0;
  flex-wrap: wrap;
}

.obs-detail__review-comment {
  flex: 1;
  min-width: 160px;
}

.obs-detail__remediation {
  margin: 10px 0;
}

.obs-detail__diff {
  margin-top: 12px;
}

.obs-detail__diff-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}

.obs-detail__diff-pre {
  margin: 0;
  padding: 10px;
  background: #0f172a;
  color: #a5f3fc;
  border-radius: 6px;
  font-size: 12px;
  line-height: 1.6;
  max-height: 320px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
