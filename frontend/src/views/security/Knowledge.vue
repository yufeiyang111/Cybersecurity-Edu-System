<template>
  <main class="knowledge-page" v-loading="loading">
    <header class="knowledge-header">
      <div>
        <el-button text :icon="ArrowLeft" @click="router.push('/security/projects')">返回项目中心</el-button>
        <p class="eyebrow">GOVERNED SECURITY KNOWLEDGE</p>
        <h1>安全知识治理</h1>
        <p>维护工作区级、版本化的安全知识来源。文档默认只以脱敏摘要参与 RAG 检索，修复建议必须附带可追溯引用。</p>
      </div>
      <div class="header-actions">
        <el-button :icon="Refresh" :loading="loading" @click="loadSources">刷新</el-button>
        <el-button type="primary" :icon="Plus" @click="sourceDialogVisible = true">新增知识源</el-button>
      </div>
    </header>

    <el-alert type="warning" :closable="false" show-icon title="治理边界：不要在知识文档中录入密钥、令牌或真实生产凭据。" class="boundary-alert">
      后端不会在列表接口返回文档正文；向量索引启用时也只接收脱敏后的文本，检索不可用会自动退化为词法检索。
    </el-alert>
    <el-alert v-if="errorMessage" type="error" :title="errorMessage" :closable="false" show-icon class="boundary-alert" />

    <section class="source-layout">
      <KnowledgeSourceList
        :sources="sources"
        :selected-source="selectedSource"
        :loading="loading"
        @select-source="selectSource"
      />
      <KnowledgeDocumentTable
        :selected-source="selectedSource"
        :documents="documents"
        :loading="documentsLoading"
        @create-document="openDocumentDialog"
      />
    </section>

    <KnowledgeSourceDialog v-model="sourceDialogVisible" :submitting="sourceSubmitting" @submit="handleCreateSource" />
    <KnowledgeDocumentDialog v-model="documentDialogVisible" :submitting="documentSubmitting" @submit="handleCreateDocument" />
  </main>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft, Plus, Refresh } from '@element-plus/icons-vue'
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
  createDocument
} = useSecurityKnowledge()

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
.knowledge-page { min-height:100vh; padding:36px clamp(20px,4vw,64px); background:#f5f7fb; color:#182230; }
.knowledge-header,.source-layout,.boundary-alert { max-width:1200px; margin-left:auto; margin-right:auto; }
.knowledge-header { display:flex; justify-content:space-between; gap:20px; align-items:flex-start; margin-bottom:20px; }
.knowledge-header h1 { margin:7px 0; font-size:clamp(30px,4vw,40px); }
.knowledge-header p { margin:0; max-width:760px; line-height:1.7; color:#657287; }
.eyebrow { margin:0; color:#147d64!important; font-size:12px; font-weight:700; letter-spacing:.12em; }
.header-actions { display:flex; gap:10px; flex-wrap:wrap; justify-content:flex-end; }
.boundary-alert { margin-bottom:18px; }
.source-layout { display:grid; grid-template-columns:minmax(280px,.8fr) minmax(0,1.7fr); gap:18px; align-items:start; }
@media(max-width:820px){ .knowledge-header{flex-direction:column}.header-actions{justify-content:flex-start}.source-layout{grid-template-columns:1fr} }
</style>
