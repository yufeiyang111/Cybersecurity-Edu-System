<template>
  <main class="knowledge-page">
    <header class="knowledge-header">
      <div class="header-left">
        <button class="breadcrumb" type="button" @click="router.push('/security/projects')">
          <BaseIcon name="arrow-left" :size="14" />
          返回项目中心
        </button>
        <p class="page-eyebrow">GOVERNED SECURITY KNOWLEDGE</p>
        <h1 class="page-title">安全知识治理</h1>
        <p class="page-desc">
          维护工作区级、版本化的安全知识库。文档默认只以脱敏摘要参与 RAG 检索，按建议必须附带可追溯引用。
        </p>
      </div>
      <div class="header-actions">
        <button class="icon-btn" type="button" title="刷新" :disabled="loading" @click="loadSources">
          <BaseIcon name="refresh" :size="16" />
        </button>
        <BaseButton variant="primary" @click="sourceDialogVisible = true">
          <BaseIcon name="plus" :size="14" />
          新增知识源
        </BaseButton>
      </div>
    </header>

    <div class="alert-banner">
      <BaseIcon name="alert-triangle" :size="18" class="alert-icon" />
      <div class="alert-content">
        <div class="alert-title">治理边界</div>
        <div class="alert-body">
          不要在知识文档中录入密钥、令牌或真实生产式数据。<br>
          后端不会在列表接口返回文档正文；内置索引切片时也只返回脱敏后的文本，检索不会自动退化为词法检索。
        </div>
      </div>
    </div>

    <div v-if="errorMessage" class="error-banner">
      <BaseIcon name="alert-triangle" :size="16" />
      {{ errorMessage }}
    </div>

    <section class="source-layout">
      <div v-loading="loading">
        <KnowledgeSourceList
          :sources="sources"
          :selected-source="selectedSource"
          :loading="loading"
          @select-source="selectSource"
        />
      </div>
      <div v-loading="documentsLoading">
        <KnowledgeDocumentTable
          :selected-source="selectedSource"
          :documents="documents"
          :loading="documentsLoading"
          @create-document="openDocumentDialog"
        />
      </div>
    </section>

    <div class="ai-fab">
      <transition name="bubble">
        <div v-if="aiMessage" class="ai-bubble">
          {{ aiMessage }}
        </div>
      </transition>
      <button class="ai-avatar" type="button" title="AI 安全助手" @click="router.push('/qa')">
        <BaseIcon name="edit" :size="18" />
      </button>
    </div>

    <KnowledgeSourceDialog v-model="sourceDialogVisible" :submitting="sourceSubmitting" @submit="handleCreateSource" />
    <KnowledgeDocumentDialog v-model="documentDialogVisible" :submitting="documentSubmitting" @submit="handleCreateDocument" />
  </main>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { BaseIcon, BaseButton } from '@/components/ui'
import KnowledgeDocumentDialog from '@/components/security/knowledge/KnowledgeDocumentDialog.vue'
import KnowledgeDocumentTable from '@/components/security/knowledge/KnowledgeDocumentTable.vue'
import KnowledgeSourceDialog from '@/components/security/knowledge/KnowledgeSourceDialog.vue'
import KnowledgeSourceList from '@/components/security/knowledge/KnowledgeSourceList.vue'
import { useSecurityKnowledge } from '@/composables/security/useSecurityKnowledge'
import { securityApiErrorMessage } from '@/features/security/presentation'

const router = useRouter()

const sourceDialogVisible = ref(false)
const documentDialogVisible = ref(false)
const sourceSubmitting = ref(false)
const documentSubmitting = ref(false)

const {
  loading,
  documentsLoading,
  errorMessage,
  sources,
  documents,
  selectedSource,
  loadSources,
  selectSource,
  createSource,
  createDocument,
} = useSecurityKnowledge()

const aiMessage = ref('检测到 1 条知识更新建议：OWASP Top 10 2025 已发布，建议更新相关知识库文档。')

const openDocumentDialog = () => {
  if (selectedSource.value) documentDialogVisible.value = true
}

const handleCreateSource = async (payload) => {
  if (sourceSubmitting.value) return
  sourceSubmitting.value = true
  try {
    await createSource(payload)
    sourceDialogVisible.value = false
    ElMessage.success('安全知识源已创建')
  } catch (error) {
    ElMessage.error(securityApiErrorMessage(error, '创建安全知识源失败'))
  } finally {
    sourceSubmitting.value = false
  }
}

const handleCreateDocument = async (payload) => {
  if (documentSubmitting.value) return
  documentSubmitting.value = true
  try {
    await createDocument(payload)
    documentDialogVisible.value = false
    ElMessage.success('版本化安全知识文档已创建')
  } catch (error) {
    ElMessage.error(securityApiErrorMessage(error, '创建安全知识文档失败'))
  } finally {
    documentSubmitting.value = false
  }
}

onMounted(loadSources)
</script>

<style scoped lang="scss">
.knowledge-page {
  min-height: 100vh;
  padding: 28px 32px 80px;
  background: #ffffff;
  color: #0f172a;
}

.knowledge-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 20px;
  margin-bottom: 20px;
  max-width: 1200px;
}

.header-left { flex: 1; min-width: 0; }

.breadcrumb {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #2563eb;
  background: none;
  border: none;
  cursor: pointer;
  padding: 0;
  margin-bottom: 8px;
  text-align: left;
}
.breadcrumb:hover { text-decoration: underline; }

.page-eyebrow {
  margin: 0 0 6px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 1px;
  text-transform: uppercase;
  color: #94a3b8;
}

.page-title {
  margin: 0 0 8px;
  font-size: 24px;
  font-weight: 700;
  color: #0f172a;
}

.page-desc {
  margin: 0;
  font-size: 13.5px;
  color: #475569;
  max-width: 640px;
  line-height: 1.6;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}

.icon-btn {
  width: 34px;
  height: 34px;
  border-radius: 6px;
  border: 1px solid #e2e8f0;
  background: #ffffff;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: #475569;
  transition: background 0.15s;
}
.icon-btn:hover:not(:disabled) { background: #f1f5f9; }
.icon-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.alert-banner {
  background: #fffbeb;
  border: 1px solid #fde68a;
  border-radius: 8px;
  padding: 14px 16px;
  display: flex;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 20px;
  max-width: 1200px;
}

.alert-icon { color: #d97706; flex-shrink: 0; margin-top: 1px; }

.alert-content {}

.alert-title {
  font-weight: 600;
  color: #0f172a;
  margin-bottom: 4px;
  font-size: 14px;
}

.alert-body {
  font-size: 13px;
  color: #475569;
  line-height: 1.6;
}

.error-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 8px;
  padding: 12px 16px;
  margin-bottom: 16px;
  color: #dc2626;
  font-size: 13px;
  max-width: 1200px;
}

.source-layout {
  display: grid;
  grid-template-columns: minmax(280px, 1fr) minmax(0, 2fr);
  gap: 16px;
  align-items: start;
  max-width: 1200px;
}

.ai-fab {
  position: fixed;
  right: 24px;
  bottom: 24px;
  z-index: 200;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 10px;
}

.ai-bubble {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 12px 12px 4px 12px;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.12);
  padding: 12px 14px;
  font-size: 12.5px;
  color: #475569;
  max-width: 320px;
  line-height: 1.65;
}

.ai-avatar {
  width: 42px;
  height: 42px;
  border-radius: 50%;
  border: none;
  background: #2563eb;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  box-shadow: 0 4px 14px rgba(37, 99, 235, 0.35);
  transition: transform 0.15s ease;
}
.ai-avatar:hover { transform: scale(1.06); }

.bubble-enter-active, .bubble-leave-active { transition: all 0.2s ease; }
.bubble-enter-from, .bubble-leave-to { opacity: 0; transform: translateY(8px); }

@media (max-width: 900px) {
  .source-layout { grid-template-columns: 1fr; }
  .knowledge-header { flex-direction: column; }
  .header-actions { width: 100%; justify-content: flex-end; }
}

@media (max-width: 640px) {
  .knowledge-page { padding: 20px 16px 80px; }
  .page-title { font-size: 20px; }
}
</style>
