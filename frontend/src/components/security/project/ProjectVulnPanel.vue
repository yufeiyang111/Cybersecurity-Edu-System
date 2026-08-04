<template>
  <section class="vp" v-loading="loading">
    <div class="vp-head">
      <div class="vp-title">
        <h3>{{ project.name }} · 漏洞详情</h3>
        <span v-if="project.vulns" class="vp-count">共 {{ project.vulns.total }} 条</span>
      </div>
      <button class="vp-close" type="button" @click="$emit('close')">
        <el-icon><Close /></el-icon>
      </button>
    </div>

    <div class="vp-body">
      <template v-if="findings.length === 0">
        <div class="vp-empty">
          <el-empty :description="loading ? '正在加载漏洞详情…' : '该次扫描未发现安全漏洞'" :image-size="72" />
        </div>
      </template>

      <article v-for="finding in findings" :key="finding.id" class="finding">
        <div class="finding-head">
          <span class="sev-badge" :class="`sev-${finding.severity}`">{{ severityLabel(finding.severity) }}</span>
          <span class="finding-rule">{{ finding.rule_id }}</span>
          <span class="finding-loc">{{ finding.file_path }}:{{ finding.start_line }}</span>
        </div>
        <p class="vp-desc">{{ finding.message }}</p>

        <template v-if="evidenceFor(finding)">
          <p class="vp-sec-label">问题代码定位</p>
          <div class="code-block">
            <div
              v-for="(line, index) in evidenceFor(finding).content.split('\n')"
              :key="index"
              class="code-line"
              :class="{ 'code-line--hl': isVulnLine(finding, evidenceFor(finding), index) }"
            >
              <span class="code-ln">{{ evidenceFor(finding).start_line + index }}</span>
              <span class="code-text">{{ line }}</span>
            </div>
          </div>
          <p class="vp-code-note">以上为脱敏证据片段，完整源码仅在受控分析边界内处理。</p>
        </template>

        <div class="vp-related">
          <div class="rel-item"><div class="k">CWE</div><div class="v">{{ finding.cwe_id || '—' }}</div></div>
          <div class="rel-item"><div class="k">发现时间</div><div class="v">{{ formatDate(finding.created_at) }}</div></div>
          <div class="rel-item"><div class="k">扫描引擎</div><div class="v">{{ finding.rule_version || finding.category }}</div></div>
          <div class="rel-item"><div class="k">状态</div><div class="v">{{ statusLabel(finding.status) }}</div></div>
        </div>

        <div class="fix-card">
          <div class="fix-title">
            <el-icon><CircleCheck /></el-icon>
            <span>修复方案</span>
          </div>
          <p class="fix-desc">已为该发现生成可审核的修复建议（含依据、修复步骤与补丁预览）。</p>
          <el-button size="small" type="success" plain @click="$emit('open-detail', finding)">查看修复建议</el-button>
        </div>
      </article>
    </div>
  </section>
</template>

<script setup>
import { CircleCheck, Close } from '@element-plus/icons-vue'

const props = defineProps({
  project: { type: Object, required: true },
  findings: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false }
})

defineEmits(['close', 'open-detail'])

const severityDefinitions = {
  critical: '严重',
  high: '高危',
  medium: '中危',
  low: '低危',
  info: '提示'
}

const statusDefinitions = {
  open: '待处理',
  triaged: '已分诊',
  accepted_risk: '风险接受',
  false_positive: '误报',
  resolved: '已修复'
}

const severityLabel = (severity) => severityDefinitions[severity] || severity
const statusLabel = (status) => statusDefinitions[status] || status || '—'

const evidenceFor = (finding) => {
  const evidence = finding.evidence || []
  const code = evidence.find((item) => item.type === 'code' && item.content)
  return code || evidence.find((item) => item.content) || null
}

const isVulnLine = (finding, evidence, index) => {
  const lineNumber = (evidence.start_line || 0) + index
  if (finding.end_line) {
    return lineNumber >= (finding.start_line || 0) && lineNumber <= finding.end_line
  }
  return lineNumber === (finding.start_line || 0)
}

const formatDate = (value) => {
  if (!value) return '—'
  const date = new Date(value)
  const pad = (n) => String(n).padStart(2, '0')
  return `${date.getFullYear()}/${pad(date.getMonth() + 1)}/${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}
</script>

<style scoped lang="scss">
.vp {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  overflow: hidden;
}

.vp-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 14px 18px;
  border-bottom: 1px solid #e2e8f0;
  background: #f1f5f9;
}

.vp-title {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;

  h3 {
    font-size: 14.5px;
    font-weight: 600;
    margin: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .vp-count {
    font-size: 12px;
    color: #475569;
    white-space: nowrap;
  }
}

.vp-close {
  width: 28px;
  height: 28px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: #94a3b8;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  cursor: pointer;

  &:hover {
    background: #e2e8f0;
    color: #0f172a;
  }
}

.vp-body {
  padding: 16px 18px 18px;
}

.vp-empty {
  padding: 8px 0 4px;
}

.finding + .finding {
  margin-top: 18px;
  padding-top: 18px;
  border-top: 1px solid #f1f5f9;
}

.finding-head {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.sev-badge {
  font-size: 11.5px;
  font-weight: 600;
  color: #fff;
  padding: 2px 9px;
  border-radius: 4px;
  white-space: nowrap;
}

.sev-critical { background: #dc2626; }
.sev-high { background: #ea580c; }
.sev-medium { background: #ca8a04; }
.sev-low { background: #16a34a; }
.sev-info { background: #64748b; }

.finding-rule {
  font-family: "SF Mono", "Cascadia Code", Consolas, Menlo, monospace;
  font-size: 12px;
  color: #2563eb;
  background: #eff6ff;
  border-radius: 4px;
  padding: 1px 6px;
}

.finding-loc {
  font-size: 12px;
  color: #94a3b8;
  font-family: "SF Mono", "Cascadia Code", Consolas, Menlo, monospace;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 60%;
}

.vp-desc {
  margin: 8px 0 0;
  font-size: 13.5px;
  color: #475569;
  line-height: 1.7;
}

.vp-sec-label {
  margin: 16px 0 8px;
  font-size: 12.5px;
  font-weight: 600;
  color: #0f172a;
}

.code-block {
  background: #0f172a;
  border-radius: 8px;
  overflow-x: auto;
  padding: 12px 0;
  font-family: "SF Mono", "Cascadia Code", Consolas, "Liberation Mono", Menlo, monospace;
  font-size: 12.5px;
  line-height: 1.7;
}

.code-line {
  display: flex;
  min-height: 21px;

  &--hl {
    background: rgba(220, 38, 38, 0.22);

    .code-text {
      color: #fecaca;
    }
  }
}

.code-ln {
  width: 56px;
  flex-shrink: 0;
  text-align: right;
  padding-right: 14px;
  color: #64748b;
  user-select: none;
}

.code-text {
  padding-right: 14px;
  color: #cbd5e1;
  white-space: pre;
}

.vp-code-note {
  margin: 6px 0 0;
  font-size: 11.5px;
  color: #94a3b8;
}

.vp-related {
  margin-top: 16px;
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
}

.rel-item {
  background: #f1f5f9;
  border-radius: 6px;
  padding: 9px 12px;
  min-width: 0;

  .k {
    font-size: 11px;
    color: #94a3b8;
  }

  .v {
    margin-top: 2px;
    font-size: 12.5px;
    font-weight: 600;
    color: #0f172a;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}

.fix-card {
  margin-top: 10px;
  background: #f0fdf4;
  border: 1px solid #bbf7d0;
  border-radius: 8px;
  padding: 14px 16px;

  .fix-title {
    display: flex;
    align-items: center;
    gap: 7px;
    font-size: 13px;
    font-weight: 600;
    color: #166534;
  }

  .fix-desc {
    margin: 6px 0 10px;
    font-size: 12.5px;
    color: #4d7c0f;
    line-height: 1.6;
  }
}

@media (max-width: 720px) {
  .vp-related {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
