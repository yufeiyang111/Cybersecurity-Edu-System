<template>
  <div class="policy-editor-page">
    <div class="page-heading animate-fadeIn">
      <h2>政策文档管理</h2>
      <el-button
        type="primary"
        :loading="loading"
        @click="loadList"
      >
        <el-icon>
          <Refresh />
        </el-icon>
        刷新列表
      </el-button>
    </div>

    <div class="policy-editor-layout">
      <el-card
        class="panel-card list-card animate-fadeIn"
        shadow="never"
        style="animation-delay: 0.1s"
      >
        <template #header>
          <div class="panel-card__header">
            <span>文档列表</span>
            <span class="panel-card__header-count">共 {{ policies.length }} 篇</span>
          </div>
        </template>

        <div v-loading="loading" class="policy-list-wrap">
          <ul v-if="policies.length" class="policy-list">
            <li
              v-for="item in policies"
              :key="item.slug"
              class="policy-list__item"
              :class="{ 'policy-list__item--active': item.slug === activeSlug }"
              @click="selectPolicy(item)"
            >
              <div class="policy-list__main">
                <div class="policy-list__title">
                  <span class="policy-list__icon">
                    <el-icon>
                      <Document />
                    </el-icon>
                  </span>
                  <span class="policy-list__name">{{ item.title }}</span>
                </div>
                <span class="policy-list__meta">
                  v{{ item.version }} · {{ formatDate(item.updated_at) }}
                </span>
              </div>
              <span class="policy-list__version">v{{ item.version }}</span>
            </li>
          </ul>
          <div v-else class="policy-list-empty">
            <el-empty description="暂无政策文档" :image-size="80" />
          </div>
        </div>
      </el-card>

      <el-card
        class="panel-card editor-card animate-fadeIn"
        shadow="never"
        style="animation-delay: 0.18s"
        v-loading="editorLoading"
      >
        <template v-if="form.title || form.content">
          <div class="editor-toolbar">
            <div class="editor-toolbar__info">
              <div class="editor-toolbar__title">
                <span class="editor-toolbar__icon">
                  <el-icon>
                    <EditPen />
                  </el-icon>
                </span>
                <span>{{ form.title || '未命名' }}</span>
              </div>
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
                <el-icon>
                  <Check />
                </el-icon>
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
                :rows="40"
                placeholder="支持 Markdown 语法..."
              />
              <div v-else class="editor-preview">
                <MarkdownRenderer :content="form.content" sanitize />
              </div>
            </el-form-item>
          </el-form>
        </template>

        <div v-else class="editor-empty">
          <el-empty description="请选择左侧文档进行编辑" :image-size="90" />
        </div>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, Document, EditPen, Check } from '@element-plus/icons-vue'
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
    policies.value = result.policies || []
    if (policies.value.length > 0 && !activeSlug.value) {
      selectPolicy(policies.value[0])
    }
  } catch (e) {
    ElMessage.error('加载政策文档失败')
  } finally {
    loading.value = false
  }
}

let policyLoadSequence = 0

async function selectPolicy(item) {
  const sequence = ++policyLoadSequence
  activeSlug.value = item.slug
  mode.value = 'edit'
  editorLoading.value = true
  try {
    const result = await policyAPI.get(item.slug)
    if (sequence !== policyLoadSequence) return
    current.value = result.policy
    form.value.title = result.policy.title
    form.value.content = result.policy.content || ''
  } catch (e) {
    if (sequence !== policyLoadSequence) return
    ElMessage.error('加载文档内容失败')
  } finally {
    if (sequence === policyLoadSequence) {
      editorLoading.value = false
    }
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
.policy-editor-page {
  // ==================== 页面标题行 ====================
  .page-heading {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    margin-bottom: 16px;

    h2 {
      margin: 0;
      font-size: 20px;
      font-weight: 700;
      color: #1f2937;
    }
  }

  // ==================== 布局 ====================
  .policy-editor-layout {
    display: grid;
    grid-template-columns: 320px minmax(0, 1fr);
    gap: 16px;
    align-items: stretch;

    @media (max-width: 900px) {
      grid-template-columns: 1fr;
    }
  }

  // ==================== 内容卡片 ====================
  .panel-card {
    border-radius: 12px;
    border: 1px solid #e6e8eb;
    transition: transform 0.25s ease, box-shadow 0.25s ease;

    :deep(.el-card__header) {
      background: #fff;
      border-bottom-color: #e6e8eb;
    }

    &:hover {
      transform: translateY(-3px);
      box-shadow: 0 12px 28px rgba(15, 23, 42, 0.08);
    }
  }

  .panel-card__header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-weight: 600;
    color: #303133;
  }

  .panel-card__header-count {
    font-size: 12px;
    font-weight: 400;
    color: #909399;
  }

  // ==================== 左侧列表 ====================
  .list-card {
    :deep(.el-card__body) {
      padding: 0;
    }
  }

  .policy-list-wrap {
    min-height: 720px;
    padding: 10px;
  }

  .policy-list {
    margin: 0;
    padding: 0;
    list-style: none;
  }

  .policy-list__item {
    position: relative;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    padding: 12px 14px;
    border-radius: 8px;
    cursor: pointer;
    transition: background 0.2s ease;

    &:hover {
      background: #f6f8fa;
    }

    &--active {
      background: #eff6ff;

      .policy-list__name {
        color: #2563eb;
        font-weight: 600;
      }

      .policy-list__version {
        background: rgba(37, 99, 235, 0.1);
        color: #2563eb;
        border-color: rgba(37, 99, 235, 0.25);
      }
    }
  }

  .policy-list__main {
    display: flex;
    flex-direction: column;
    gap: 4px;
    min-width: 0;
  }

  .policy-list__title {
    display: flex;
    align-items: center;
    gap: 8px;
    min-width: 0;
  }

  .policy-list__icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 26px;
    height: 26px;
    border-radius: 7px;
    background: #eef2ff;
    color: #4f46e5;
    flex-shrink: 0;
  }

  .policy-list__name {
    font-size: 14px;
    color: #303133;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    transition: color 0.15s ease;
  }

  .policy-list__meta {
    font-size: 12px;
    color: #909399;
  }

  .policy-list__version {
    flex-shrink: 0;
    padding: 2px 8px;
    border: 1px solid #e6e8eb;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 600;
    color: #909399;
    transition: all 0.2s ease;
  }

  .policy-list-empty {
    padding: 40px 0;
  }

  // ==================== 右侧编辑器 ====================
  .editor-card {
    :deep(.el-card__body) {
      display: flex;
      flex-direction: column;
    }
  }

  .editor-toolbar {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 16px;
    margin-bottom: 20px;
    padding-bottom: 16px;
    border-bottom: 1px solid #e6e8eb;
  }

  .editor-toolbar__info {
    display: flex;
    flex-direction: column;
    gap: 4px;
    min-width: 0;
  }

  .editor-toolbar__title {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 16px;
    font-weight: 700;
    color: #303133;
  }

  .editor-toolbar__icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 30px;
    height: 30px;
    border-radius: 8px;
    background: #d1fae5;
    color: #059669;
    flex-shrink: 0;
  }

  .editor-toolbar__meta {
    font-size: 12px;
    color: #909399;
  }

  .editor-toolbar__actions {
    display: flex;
    align-items: center;
    gap: 12px;
    flex-shrink: 0;
  }

  .editor-preview {
    width: 100%;
    min-height: 720px;
    padding: 16px 20px;
    border: 1px solid #e6e8eb;
    border-radius: 8px;
    background: #fff;
  }

  .editor-empty {
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 720px;
  }
}

@media (max-width: 768px) {
  .policy-editor-page {
    .page-heading {
      flex-wrap: wrap;

      .el-button {
        width: 100%;
      }
    }

    .editor-toolbar {
      flex-direction: column;
    }

    .editor-toolbar__actions {
      width: 100%;
      justify-content: space-between;
    }
  }
}

@media (prefers-reduced-motion: reduce) {
  .policy-editor-page {
    .panel-card {
      transition: none;
    }

    .panel-card:hover {
      transform: none;
    }

    .policy-list__item,
    .policy-list__name,
    .policy-list__version {
      transition: none;
    }
  }
}
</style>
