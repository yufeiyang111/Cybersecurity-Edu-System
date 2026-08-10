<template>
  <div class="help-doc-editor">
    <div v-if="!document" class="help-doc-editor__placeholder">
      <BaseIcon name="file-text" :size="36" />
      <p>从左侧选择一个文档进行编辑，或点击「新建文档」创建。</p>
    </div>
    <div v-else class="help-doc-editor__form">
      <div class="form-row form-row--2col">
        <label class="form-field">
          <span class="form-label">标题</span>
          <input
            v-model="form.title"
            type="text"
            class="form-input"
            maxlength="200"
            placeholder="文档标题"
          />
        </label>
        <label class="form-field">
          <span class="form-label">所属分类</span>
          <select v-model="form.category_id" class="form-input">
            <option v-for="category in flatCategories" :key="category.id" :value="category.id">
              {{ category.label }}
            </option>
          </select>
        </label>
      </div>

      <label class="form-field">
        <span class="form-label">摘要</span>
        <input
          v-model="form.summary"
          type="text"
          class="form-input"
          maxlength="500"
          placeholder="一句话说明本文内容（显示在文档标题下方）"
        />
      </label>

      <div class="form-row">
        <label class="form-field form-field--flex">
          <span class="form-label">slug</span>
          <input
            v-model="form.slug"
            type="text"
            class="form-input"
            maxlength="96"
            placeholder="如 getting-started（仅字母数字 - _）"
          />
        </label>
        <label class="form-field form-field--flex">
          <span class="form-label">排序</span>
          <input v-model.number="form.sort_order" type="number" class="form-input form-input--number" />
        </label>
        <label class="form-check">
          <input v-model="form.is_active" type="checkbox" />
          <span>启用</span>
        </label>
      </div>

      <div class="editor-tabs">
        <button
          type="button"
          class="editor-tab"
          :class="{ 'is-active': mode === 'edit' }"
          @click="mode = 'edit'"
        >
          编辑 Markdown
        </button>
        <button
          type="button"
          class="editor-tab"
          :class="{ 'is-active': mode === 'preview' }"
          @click="mode = 'preview'"
        >
          预览
        </button>
      </div>

      <textarea
        v-if="mode === 'edit'"
        v-model="form.content"
        class="editor-textarea"
        rows="18"
        placeholder="# 标题&#10;&#10;支持 Markdown：多级标题、表格、列表、代码块、引用等。"
      ></textarea>
      <div v-else class="editor-preview">
        <MarkdownRenderer :content="form.content" />
      </div>

      <div class="form-actions">
        <span class="form-hint">
          {{ form.content.length }} 字符
        </span>
        <BaseButton variant="primary" :loading="saving" @click="handleSave">
          {{ isNew ? '创建文档' : '保存修改' }}
        </BaseButton>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { BaseIcon, BaseButton } from '@/components/ui'
import MarkdownRenderer from '@/components/MarkdownRenderer.vue'

const props = defineProps({
  document: {
    type: Object,
    default: null
  },
  tree: {
    type: Array,
    default: () => []
  },
  saving: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['save'])

const mode = ref('edit')
const form = reactive({
  slug: '',
  category_id: null,
  title: '',
  summary: '',
  content: '',
  sort_order: 0,
  is_active: true
})

const isNew = computed(() => !props.document?.id)

const flatCategories = computed(() => {
  const items = []
  const walk = (nodes, prefix) => {
    for (const node of nodes) {
      items.push({
        id: node.id,
        label: prefix ? `${prefix} / ${node.name}` : node.name
      })
      if (node.children && node.children.length) {
        walk(node.children, prefix ? `${prefix} / ${node.name}` : node.name)
      }
    }
  }
  walk(props.tree, '')
  return items
})

const syncForm = (document) => {
  if (!document) return
  form.slug = document.slug || ''
  form.category_id = document.category_id ?? null
  form.title = document.title || ''
  form.summary = document.summary || ''
  form.content = document.content || ''
  form.sort_order = document.sort_order || 0
  form.is_active = document.is_active ?? true
  mode.value = 'edit'
}

watch(
  () => props.document,
  (document) => {
    if (document?.id) {
      syncForm(document)
    } else if (document) {
      // 新建：带默认分类
      form.slug = ''
      form.category_id = document.category_id ?? flatCategories.value[0]?.id ?? null
      form.title = ''
      form.summary = ''
      form.content = ''
      form.sort_order = 0
      form.is_active = true
      mode.value = 'edit'
    }
  },
  { immediate: true }
)

const handleSave = () => {
  if (!form.title.trim()) {
    ElMessage.warning('请填写文档标题')
    return
  }
  if (!form.slug.trim()) {
    ElMessage.warning('请填写 slug')
    return
  }
  if (!form.content.trim()) {
    ElMessage.warning('请填写文档正文')
    return
  }
  if (!form.category_id) {
    ElMessage.warning('请选择所属分类')
    return
  }
  emit('save', {
    slug: form.slug.trim(),
    category_id: form.category_id,
    title: form.title.trim(),
    summary: form.summary.trim(),
    content: form.content,
    sort_order: form.sort_order,
    is_active: form.is_active
  })
}
</script>

<style scoped lang="scss">
.help-doc-editor {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 20px;
  min-height: 420px;

  &__placeholder {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 12px;
    height: 380px;
    color: #94a3b8;

    p {
      margin: 0;
      font-size: 13.5px;
    }
  }

  &__form {
    display: flex;
    flex-direction: column;
    gap: 14px;
  }
}

.form-row {
  display: flex;
  gap: 14px;

  &--2col {
    display: grid;
    grid-template-columns: 1.5fr 1fr;
  }
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: 6px;

  &--flex {
    flex: 1;
  }
}

.form-label {
  font-size: 12.5px;
  font-weight: 600;
  color: #475569;
}

.form-input {
  height: 36px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 0 12px;
  font-size: 13.5px;
  color: #0f172a;
  background: #fff;
  outline: none;

  &:focus {
    border-color: #2563eb;
    box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.12);
  }

  &--number {
    width: 80px;
  }
}

.form-check {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13.5px;
  color: #475569;
  padding-top: 26px;
  cursor: pointer;
}

.editor-tabs {
  display: flex;
  gap: 0;
  border-bottom: 1px solid #e2e8f0;
}

.editor-tab {
  padding: 8px 16px;
  border: none;
  background: none;
  font-size: 13.5px;
  color: #64748b;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;

  &.is-active {
    color: #2563eb;
    border-bottom-color: #2563eb;
    font-weight: 600;
  }
}

.editor-textarea {
  min-height: 320px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 12px;
  font-size: 13.5px;
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
  line-height: 1.7;
  color: #0f172a;
  resize: vertical;
  outline: none;

  &:focus {
    border-color: #2563eb;
  }
}

.editor-preview {
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 16px;
  min-height: 320px;
  overflow-x: auto;
}

.form-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.form-hint {
  font-size: 12.5px;
  color: #94a3b8;
}

@media (max-width: 768px) {
  .form-row,
  .form-row--2col {
    grid-template-columns: 1fr;
    flex-direction: column;
  }

  .form-check {
    padding-top: 0;
  }
}
</style>