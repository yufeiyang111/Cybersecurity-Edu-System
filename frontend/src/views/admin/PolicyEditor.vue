<template>
  <div class="policy-editor-page">
    <h2 class="page-title">政策文档管理</h2>

    <div class="policy-editor-layout">
      <el-card class="policy-editor-layout__list" v-loading="loading">
        <template #header>
          <span>文档列表</span>
        </template>
        <ul class="policy-list">
          <li
            v-for="item in policies"
            :key="item.slug"
            class="policy-list__item"
            :class="{ 'policy-list__item--active': item.slug === activeSlug }"
            @click="selectPolicy(item)"
          >
            <div class="policy-list__name">
              <el-icon><Document /></el-icon>
              <span>{{ item.title }}</span>
            </div>
            <span class="policy-list__version">v{{ item.version }}</span>
          </li>
        </ul>
      </el-card>

      <el-card class="policy-editor-layout__editor" v-loading="editorLoading">
        <template v-if="form.title || form.content">
          <div class="editor-toolbar">
            <div class="editor-toolbar__info">
              <span class="editor-toolbar__title">{{ form.title || '未命名' }}</span>
              <span v-if="current" class="editor-toolbar__meta">
                v{{ current.version }} · {{ current.updated_by || 'system' }} 更新
                · {{ formatDate(current.updated_at) }}
              </span>
            </div>
            <div class="editor-toolbar__actions">
              <el-radio-group v-model="mode" size="small">
                <el-radio-button value="edit">编辑</el-radio-button>
                <el-radio-button value="preview">预览</el-radio-button>
              </el-radio-group>
              <el-button type="primary" size="small" :loading="saving" @click="handleSave">
                保存
              </el-button>
            </div>
          </div>

          <el-form label-position="top" @submit.prevent>
            <el-form-item label="标题">
              <el-input v-model="form.title" maxlength="200" show-word-limit />
            </el-form-item>
            <el-form-item label="正文（Markdown）">
              <el-input
                v-if="mode === 'edit'"
                v-model="form.content"
                type="textarea"
                :rows="22"
                placeholder="支持 Markdown 语法..."
              />
              <div v-else class="editor-preview">
                <MarkdownRenderer :content="form.content" sanitize />
              </div>
            </el-form-item>
          </el-form>
        </template>

        <el-empty v-else description="请选择左侧文档进行编辑" />
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Document } from '@element-plus/icons-vue'
import MarkdownRenderer from '@/components/MarkdownRenderer.vue'
import { policyAPI } from '@/api'

const loading = ref(false)
const editorLoading = ref(false)
const saving = ref(false)
const policies = ref([])
const current = ref(null)
const activeSlug = ref('')
const form = ref({ title: '', content: '' })
const mode = ref('edit')

function formatDate(value) {
  if (!value) return ''
  const date = new Date(value)
  const pad = (n) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

async function loadList() {
  loading.value = true
  try {
    const result = await policyAPI.list()
    policies.value = result.policies
    if (policies.value.length > 0 && !activeSlug.value) {
      selectPolicy(policies.value[0])
    }
  } catch (e) {
    ElMessage.error('加载政策文档失败')
  } finally {
    loading.value = false
  }
}

async function selectPolicy(item) {
  activeSlug.value = item.slug
  mode.value = 'edit'
  editorLoading.value = true
  try {
    const result = await policyAPI.get(item.slug)
    current.value = result.policy
    form.value.title = result.policy.title
    form.value.content = result.policy.content
  } catch (e) {
    ElMessage.error('加载文档内容失败')
  } finally {
    editorLoading.value = false
  }
}

async function handleSave() {
  if (!form.value.title.trim()) {
    ElMessage.warning('标题不能为空')
    return
  }
  if (!form.value.content.trim()) {
    ElMessage.warning('正文内容不能为空')
    return
  }

  saving.value = true
  try {
    const result = await policyAPI.update(activeSlug.value, {
      title: form.value.title.trim(),
      content: form.value.content
    })
    current.value = result.policy
    ElMessage.success('保存成功')
    loadList()
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '保存失败')
  } finally {
    saving.value = false
  }
}

loadList()
</script>

<style lang="scss" scoped>
.policy-editor-layout {
  display: grid;
  grid-template-columns: 300px 1fr;
  gap: 16px;
  align-items: start;

  @media (max-width: 900px) {
    grid-template-columns: 1fr;
  }
}

.policy-list {
  margin: 0;
  padding: 0;
  list-style: none;

  &__item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 14px;
    border-radius: 8px;
    cursor: pointer;
    color: #606266;
    transition: background 0.2s ease, color 0.2s ease;

    &:hover {
      background: #f5f7fa;
    }

    &--active {
      background: #ecfdf5;
      color: #10b981;
    }
  }

  &__name {
    display: flex;
    align-items: center;
    gap: 8px;
    font-weight: 600;
  }

  &__version {
    font-size: 12px;
    color: #9a9a92;
  }
}

.editor-toolbar {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid #ebeef5;

  &__info {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  &__title {
    font-size: 16px;
    font-weight: 700;
    color: #303133;
  }

  &__meta {
    font-size: 12px;
    color: #9a9a92;
  }

  &__actions {
    display: flex;
    align-items: center;
    gap: 12px;
    flex-shrink: 0;
  }
}

.editor-preview {
  width: 100%;
  min-height: 320px;
  padding: 16px 20px;
  border: 1px solid #dcdfe6;
  border-radius: 8px;
  background: #fff;
}
</style>
