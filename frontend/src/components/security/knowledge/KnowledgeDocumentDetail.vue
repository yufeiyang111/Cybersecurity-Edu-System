<template>
  <article class="detail-panel">
    <header class="detail-header">
      <div class="detail-info">
        <div class="detail-title">{{ document.title }}</div>
        <div class="detail-meta">
          <BaseBadge type="blue">{{ document.document_version }}</BaseBadge>
          <BaseBadge v-for="tag in (document.tags || [])" :key="tag" type="gray">{{ tag }}</BaseBadge>
          <span class="detail-meta-text">来源：{{ document.source_name }}</span>
          <span class="detail-meta-text">更新：{{ formatDate(document.updated_at) }} · {{ document.updater_name || '未知' }}</span>
        </div>
      </div>
      <div class="detail-actions">
        <BaseButton variant="ghost" size="sm">
          <BaseIcon name="edit" :size="13" />编辑
        </BaseButton>
        <BaseButton variant="ghost" size="sm">
          <BaseIcon name="history" :size="13" />历史版本
        </BaseButton>
      </div>
    </header>

    <div class="detail-body">
      <p class="detail-summary">{{ document.summary || '暂无文档摘要。' }}</p>

      <div v-if="document.sections && document.sections.length > 0" class="detail-sections">
        <div v-for="section in document.sections" :key="section.title" class="detail-section">
          <div class="detail-section-title">{{ section.title }}</div>
          <p>{{ section.content }}</p>
          <pre v-if="section.code" class="code-block"><code>{{ section.code }}</code></pre>
        </div>
      </div>

      <div v-if="document.version_history && document.version_history.length > 0" class="version-history">
        <div class="version-history-title">版本历史</div>
        <div v-for="(ver, idx) in document.version_history" :key="ver.version" class="version-item">
          <div class="version-dot-wrap">
            <div class="version-dot" :class="{ current: idx === 0 }" />
            <div v-if="idx < document.version_history.length - 1" class="version-line" />
          </div>
          <div class="version-info">
            <div class="version-header">
              <span class="version-num">{{ ver.version }}</span>
              <BaseBadge v-if="idx === 0" type="green">当前版本</BaseBadge>
            </div>
            <div class="version-desc">{{ ver.description }}</div>
            <div class="version-time">{{ ver.updated_at }} · {{ ver.updater_name }}</div>
          </div>
        </div>
      </div>
    </div>
  </article>
</template>

<script setup>
import { BaseIcon, BaseBadge, BaseButton } from '@/components/ui'

defineProps({
  document: { type: Object, required: true },
})

function formatDate(val) {
  if (!val) return ''
  const d = new Date(val)
  const now = new Date()
  const diff = now - d
  const mins = Math.floor(diff / 60000)
  const hours = Math.floor(diff / 3600000)
  const days = Math.floor(diff / 86400000)
  if (mins < 1) return '刚刚'
  if (mins < 60) return `${mins}分钟前`
  if (hours < 24) return `${hours}小时前`
  if (days < 7) return `${days}天前`
  return d.toLocaleDateString('zh-CN')
}
</script>

<style scoped lang="scss">
.detail-panel {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  overflow: hidden;
  margin-top: 16px;
}

.detail-header {
  padding: 16px 20px;
  border-bottom: 1px solid #e2e8f0;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.detail-info { flex: 1; min-width: 0; }

.detail-title {
  font-size: 16px;
  font-weight: 600;
  color: #0f172a;
  margin-bottom: 8px;
}

.detail-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.detail-meta-text {
  font-size: 12px;
  color: #94a3b8;
}

.detail-actions { display: flex; gap: 8px; flex-shrink: 0; }

.detail-body { padding: 20px; }

.detail-summary {
  font-size: 14px;
  color: #475569;
  line-height: 1.8;
  margin-bottom: 24px;
  padding-bottom: 24px;
  border-bottom: 1px solid #e2e8f0;
}

.detail-sections { margin-bottom: 24px; }

.detail-section { margin-bottom: 20px; }

.detail-section-title {
  font-size: 14px;
  font-weight: 600;
  color: #0f172a;
  margin-bottom: 10px;
}

.detail-section p {
  font-size: 14px;
  color: #475569;
  line-height: 1.8;
  margin-bottom: 10px;
}

.code-block {
  background: #0f172a;
  color: #e2e8f0;
  border-radius: 8px;
  padding: 16px 20px;
  font-family: 'SFMono-Regular', 'Consolas', monospace;
  font-size: 13px;
  line-height: 1.7;
  overflow-x: auto;
  margin-top: 8px;
}

.version-history { margin-top: 24px; padding-top: 24px; border-top: 1px solid #e2e8f0; }

.version-history-title {
  font-size: 14px;
  font-weight: 600;
  color: #0f172a;
  margin-bottom: 16px;
}

.version-item {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}

.version-dot-wrap {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex-shrink: 0;
}

.version-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #2563eb;
  flex-shrink: 0;
  margin-top: 3px;
}

.version-dot.current { background: #16a34a; }

.version-line {
  width: 2px;
  flex: 1;
  background: #e2e8f0;
  margin-top: 4px;
  min-height: 24px;
}

.version-info { flex: 1; }

.version-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.version-num { font-size: 14px; font-weight: 600; color: #0f172a; }

.version-desc { font-size: 13px; color: #475569; margin-bottom: 2px; }

.version-time { font-size: 12px; color: #94a3b8; }
</style>
