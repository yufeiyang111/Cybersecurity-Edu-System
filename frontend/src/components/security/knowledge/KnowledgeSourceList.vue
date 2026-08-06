<template>
  <BasePanel
    :title="sourcesTitle"
    :subtitle="selectedSource ? undefined : '选择一个知识来源后查看文档版本。'"
    :scroll="true"
  >
    <template #header>
      <div class="panel-title-group">
        <h3 class="panel-title">
          <BaseIcon name="layers" :size="16" />
          知识来源
          <BaseBadge v-if="sources.length > 0" type="blue">{{ sources.length }}</BaseBadge>
        </h3>
        <p class="panel-subtitle">仅工作区 Owner 或安全管理员可维护。</p>
      </div>
    </template>

    <div v-if="loading && sources.length === 0" class="loading-state">
      <div v-for="i in 3" :key="i" class="source-skeleton" />
    </div>
    <div v-else-if="sources.length === 0" class="empty-state">
      <BaseIcon name="file" :size="32" />
      <p>还没有安全知识源</p>
    </div>
    <div v-else class="source-list">
      <button
        v-for="source in sources"
        :key="source.id"
        type="button"
        class="source-item"
        :class="{ selected: selectedSource?.id === source.id }"
        @click="emit('select-source', source)"
      >
        <div class="source-icon" :style="{ background: sourceIconBg(source.source_type) }">
          <BaseIcon :name="sourceIconName(source.source_type)" :size="16" />
        </div>
        <div class="source-info">
          <div class="source-name">{{ source.name }}</div>
          <div class="source-meta">
            <span class="source-meta-item">
              <BaseIcon name="file-doc" :size="12" />
              {{ source.doc_count || 0 }}篇
            </span>
            <span class="source-meta-item">
              <BaseIcon name="clock" :size="12" />
              {{ source.last_sync_text || '从未同步' }}
            </span>
          </div>
        </div>
        <div class="source-status">
          <BaseBadge :type="sourceSyncType(source)" :dot="source.is_syncing" :pulse="source.is_syncing">
            {{ sourceSyncLabel(source) }}
          </BaseBadge>
        </div>
        <div class="source-ops" @click.stop>
          <button
            type="button"
            class="source-op-btn"
            title="编辑知识源"
            aria-label="编辑知识源"
            @click="emit('edit-source', source)"
          >
            <BaseIcon name="edit" :size="14" />
          </button>
          <button
            type="button"
            class="source-op-btn source-op-btn--danger"
            title="删除知识源"
            aria-label="删除知识源"
            @click="emit('delete-source', source)"
          >
            <BaseIcon name="trash" :size="14" />
          </button>
        </div>
      </button>
    </div>
  </BasePanel>
</template>

<script setup>
import { computed } from 'vue'
import { BaseIcon, BaseBadge, BasePanel } from '@/components/ui'

const props = defineProps({
  sources: { type: Array, default: () => [] },
  selectedSource: { type: Object, default: null },
  loading: { type: Boolean, default: false },
})

const emit = defineEmits(['select-source', 'edit-source', 'delete-source'])

const sourcesTitle = computed(() =>
  props.selectedSource ? `${props.selectedSource.name} 的文档` : '版本化文档'
)

function sourceIconName(type) {
  if (!type) return 'globe'
  const t = type.toLowerCase()
  if (t.includes('github')) return 'github'
  if (t.includes('upload') || t.includes('file')) return 'upload'
  if (t.includes('web') || t.includes('http') || t.includes('scrape')) return 'globe'
  return 'edit'
}

const ICON_BG_MAP = {
  github: '#f1f5f9',
  upload: '#dbeafe',
  globe: '#fef3c7',
  edit: '#dcfce7',
}

function sourceIconBg(type) {
  return ICON_BG_MAP[sourceIconName(type)] || '#f1f5f9'
}

function sourceSyncType(source) {
  if (source.is_syncing) return 'orange'
  if (source.is_active) return 'green'
  return 'gray'
}

function sourceSyncLabel(source) {
  if (source.is_syncing) return '同步中'
  return source.is_active ? '已同步' : '已停用'
}
</script>

<style scoped lang="scss">
.panel-title-group { flex: 1; min-width: 0; }

.panel-title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: #0f172a;
  display: flex;
  align-items: center;
  gap: 8px;
}

.panel-subtitle {
  margin: 3px 0 0;
  font-size: 12px;
  color: #94a3b8;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 40px 0;
  color: #94a3b8;
  font-size: 13px;
}

.loading-state { display: grid; gap: 10px; }

.source-skeleton {
  height: 60px;
  border-radius: 8px;
  background: linear-gradient(90deg, #f1f5f9 25%, #e2e8f0 50%, #f1f5f9 75%);
  background-size: 200% 100%;
  animation: shimmer 1.2s infinite;
}

@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

.source-list { display: grid; gap: 8px; }

.source-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  border-radius: 8px;
  cursor: pointer;
  border: 2px solid transparent;
  transition: background 0.12s;
  text-align: left;
  width: 100%;
  background: #fff;
  color: inherit;
}

.source-item:hover { background: #f8fafc; }

.source-item.selected {
  background: #eff6ff;
  border-color: #2563eb;
}

.source-icon {
  width: 32px;
  height: 32px;
  border-radius: 6px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #64748b;
}

.source-info { flex: 1; min-width: 0; }

.source-name {
  font-size: 14px;
  font-weight: 500;
  color: #0f172a;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.source-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 3px;
}

.source-meta-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: #94a3b8;
}

.source-status { flex-shrink: 0; }

.source-ops {
  display: flex;
  gap: 4px;
  flex-shrink: 0;
  opacity: 0;
  transition: opacity 0.12s;
}

.source-item:hover .source-ops {
  opacity: 1;
}

.source-op-btn {
  width: 26px;
  height: 26px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  background: #fff;
  color: #64748b;
  cursor: pointer;
  transition: background 0.12s, color 0.12s, border-color 0.12s;
}

.source-op-btn:hover {
  background: #eff6ff;
  border-color: #bfdbfe;
  color: #2563eb;
}

.source-op-btn--danger:hover {
  background: #fef2f2;
  border-color: #fecaca;
  color: #dc2626;
}
</style>
