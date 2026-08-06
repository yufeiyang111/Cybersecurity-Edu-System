<template>
  <el-dialog
    v-model="visible"
    :title="editing ? '编辑版本化安全知识文档' : '新增版本化安全知识文档'"
    width="700px"
    destroy-on-close
    @closed="resetForm"
  >
    <el-alert type="info" :closable="false" show-icon class="form-alert">
      文档正文仅用于受控检索，不会在列表接口中回显。请使用摘要化、可引用的安全指导内容。
    </el-alert>
    <el-form label-position="top" @submit.prevent="submit">
      <div class="form-grid">
        <el-form-item label="文档版本" required>
          <el-input v-model.trim="form.version" maxlength="255" placeholder="例如 2026.1-v1" />
        </el-form-item>
        <el-form-item label="标题" required>
          <el-input v-model.trim="form.title" maxlength="500" placeholder="例如 Flask 生产部署安全基线" />
        </el-form-item>
      </div>
      <el-form-item label="摘要">
        <el-input v-model.trim="form.summary" type="textarea" :rows="2" maxlength="4000" show-word-limit />
      </el-form-item>
      <el-form-item label="标签">
        <el-input v-model.trim="form.tags" maxlength="1000" placeholder="使用英文逗号分隔，例如 flask,debug,production" />
      </el-form-item>
      <el-form-item label="正文" required>
        <el-input
          v-model="form.content"
          type="textarea"
          :rows="10"
          maxlength="100000"
          show-word-limit
          placeholder="录入可审核、可追溯的安全修复指导内容。"
        />
      </el-form-item>
      <el-form-item v-if="editing" label="启用状态">
        <el-switch v-model="form.isActive" active-text="启用" inactive-text="停用" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" :disabled="!canSubmit" @click="submit">
        {{ editing ? '保存修改' : '创建文档' }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, reactive, watch } from 'vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  submitting: { type: Boolean, default: false },
  document: { type: Object, default: null }
})
const emit = defineEmits(['update:modelValue', 'submit'])
const form = reactive({
  version: '',
  title: '',
  summary: '',
  tags: '',
  content: '',
  isActive: true
})
const visible = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value)
})
const editing = computed(() => Boolean(props.document))
const canSubmit = computed(() => Boolean(form.version && form.title && form.content.trim()))

const resetForm = () => {
  Object.assign(form, {
    version: props.document?.document_version || '',
    title: props.document?.title || '',
    summary: props.document?.summary || '',
    tags: (props.document?.tags || []).join(', '),
    content: props.document?.content || '',
    isActive: props.document?.is_active ?? true
  })
}

watch(() => props.modelValue, (open) => {
  if (open) resetForm()
})

const submit = () => {
  if (!canSubmit.value || props.submitting) return
  const payload = {
    document_version: form.version,
    title: form.title,
    summary: form.summary || null,
    content: form.content,
    tags: form.tags.split(',').map((tag) => tag.trim()).filter(Boolean)
  }
  if (editing.value) payload.is_active = form.isActive
  emit('submit', payload)
}
</script>

<style scoped lang="scss">
.form-alert {
  margin-bottom: 16px;
}

.form-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 14px;
}

@media (min-width: 560px) {
  .form-grid {
    grid-template-columns: 1fr 1fr;
  }
}
</style>
