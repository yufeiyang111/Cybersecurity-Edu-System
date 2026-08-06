<template>
  <BasePanel>
    <template #header>
      <div class="panel-title-group">
        <h3 class="panel-title">
          <BaseIcon name="book" :size="16" />
          版本化文档
          <BaseBadge v-if="documents.length > 0" type="blue">{{ documents.length }}</BaseBadge>
        </h3>
        <p class="panel-subtitle">选择一个知识来源后查看文档版本。</p>
      </div>
      <div class="panel-actions">
        <BaseButton variant="ghost" size="sm" :disabled="!selectedSource" @click="emit('create-document')">
          <BaseIcon name="plus" :size="13" />
          新增文档
        </BaseButton>
      </div>
    </template>

    <div v-if="!selectedSource" class="empty-state">
      <BaseIcon name="file-text" :size="32" />
      <p>请选择左侧知识来源</p>
    </div>
    <div v-else-if="loading && documents.length === 0" class="loading-state">
      <div v-for="i in 4" :key="i" class="doc-skeleton" />
    </div>
    <div v-else-if="documents.length === 0" class="empty-state">
      <BaseIcon name="file" :size="32" />
      <p>该来源还没有版本化文档</p>
    </div>
    <div v-else class="doc-list">
      <button
        v-for="doc in documents"
        :key="doc.id"
        type="button"
        class="doc-item"
        :class="{ selected: selectedDocId === doc.id }"
        @click="selectDoc(doc)"
      >
        <div class="doc-icon">
          <BaseIcon name="file" :size="16" />
        </div>
        <div class="doc-info">
          <div class="doc-title">{{ doc.title }}</div>
          <div class="doc-meta">
            <BaseBadge type="blue">{{ doc.document_version }}</BaseBadge>
            <BaseBadge v-for="tag in (doc.tags || []).slice(0, 2)" :key="tag" type="gray">{{ tag }}</BaseBadge>
          </div>
        </div>
        <span class="doc-time">{{ formatDate(doc.updated_at) }}</span>
        <div class="doc-ops" @click.stop>
          <button
            type="button"
            class="doc-op-btn"
            title="编辑文档"
            aria-label="编辑文档"
            @click="emit('edit-document', doc)"
          >
            <BaseIcon name="edit" :size="13" />
          </button>
          <button
            type="button"
            class="doc-op-btn doc-op-btn--danger"
            title="删除文档"
            aria-label="删除文档"
            @click="emit('delete-document', doc)"
          >
            <BaseIcon name="trash" :size="13" />
          </button>
        </div>
      </button>
    </div>
  </BasePanel>

  <transition name="slide">
    <KnowledgeDocumentDetail
      v-if="selectedDoc"
      :document="selectedDoc"
      @close="selectedDocId = null"
    />
  </transition>
</template>

<script setup>
import { ref } from 'vue'
import { BaseIcon, BaseBadge, BasePanel, BaseButton } from '@/components/ui'
import KnowledgeDocumentDetail from './KnowledgeDocumentDetail.vue'

defineProps({
  selectedSource: { type: Object, default: null },
  documents: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
})

const emit = defineEmits(['create-document', 'edit-document', 'delete-document'])

const selectedDocId = ref(null)
const selectedDoc = ref(null)

function selectDoc(doc) {
  if (selectedDocId.value === doc.id) {
    selectedDocId.value = null
    selectedDoc.value = null
  } else {
    selectedDocId.value = doc.id
    selectedDoc.value = doc
  }
}

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

.panel-actions { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }

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

.loading-state { display: grid; gap: 8px; }

.doc-skeleton {
  height: 52px;
  border-radius: 8px;
  background: linear-gradient(90deg, #f1f5f9 25%, #e2e8f0 50%, #f1f5f9 75%);
  background-size: 200% 100%;
  animation: shimmer 1.2s infinite;
}

@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

.doc-list { display: grid; gap: 6px; }

.doc-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  border: 2px solid transparent;
  transition: background 0.12s;
  text-align: left;
  width: 100%;
  background: #fff;
  color: inherit;
}

.doc-item:hover { background: #f8fafc; }

.doc-item.selected {
  background: #eff6ff;
  border-color: #2563eb;
}

.doc-icon {
  width: 32px;
  height: 32px;
  border-radius: 6px;
  flex-shrink: 0;
  background: #f1f5f9;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #64748b;
}

.doc-info { flex: 1; min-width: 0; }

.doc-title {
  font-size: 14px;
  font-weight: 500;
  color: #0f172a;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.doc-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 5px;
  flex-wrap: wrap;
}

.doc-time {
  font-size: 12px;
  color: #94a3b8;
  flex-shrink: 0;
}

.doc-ops {
  display: flex;
  gap: 4px;
  flex-shrink: 0;
  opacity: 0;
  transition: opacity 0.12s;
}

.doc-item:hover .doc-ops {
  opacity: 1;
}

.doc-op-btn {
  width: 24px;
  height: 24px;
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

.doc-op-btn:hover {
  background: #eff6ff;
  border-color: #bfdbfe;
  color: #2563eb;
}

.doc-op-btn--danger:hover {
  background: #fef2f2;
  border-color: #fecaca;
  color: #dc2626;
}

.slide-enter-active, .slide-leave-active { transition: all 0.2s ease; }
.slide-enter-from, .slide-leave-to { opacity: 0; transform: translateY(-8px); }
</style>
