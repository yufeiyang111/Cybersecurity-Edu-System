<template>
  <el-dialog
    v-model="visible"
    :title="editing ? '编辑安全知识源' : '新增安全知识源'"
    width="560px"
    destroy-on-close
    @closed="resetForm"
  >
    <el-form label-position="top" @submit.prevent="submit">
      <el-form-item label="来源名称" required>
        <el-input v-model.trim="form.name" maxlength="255" placeholder="例如 OWASP ASVS" />
      </el-form-item>
      <div class="form-grid">
        <el-form-item label="来源类型" required>
          <el-input v-model.trim="form.sourceType" maxlength="64" placeholder="standard / internal / advisory" />
        </el-form-item>
        <el-form-item label="来源版本" required>
          <el-input v-model.trim="form.sourceVersion" maxlength="255" placeholder="例如 5.0" />
        </el-form-item>
      </div>
      <el-form-item label="来源地址">
        <el-input v-model.trim="form.sourceUri" maxlength="2048" placeholder="可选：不含查询参数的 HTTPS 地址" />
      </el-form-item>
      <el-form-item label="许可证">
        <el-input v-model.trim="form.licenseName" maxlength="255" placeholder="可选：例如 CC BY-SA 4.0" />
      </el-form-item>
      <el-form-item v-if="editing" label="启用状态">
        <el-switch v-model="form.isActive" active-text="启用" inactive-text="停用" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" :disabled="!canSubmit" @click="submit">
        {{ editing ? '保存修改' : '创建来源' }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, reactive, watch } from 'vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  submitting: { type: Boolean, default: false },
  source: { type: Object, default: null }
})
const emit = defineEmits(['update:modelValue', 'submit'])
const form = reactive({
  name: '',
  sourceType: 'standard',
  sourceVersion: '',
  sourceUri: '',
  licenseName: '',
  isActive: true
})
const visible = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value)
})
const editing = computed(() => Boolean(props.source))
const canSubmit = computed(() => Boolean(form.name && form.sourceType && form.sourceVersion))

const resetForm = () => {
  Object.assign(form, {
    name: props.source?.name || '',
    sourceType: props.source?.source_type || 'standard',
    sourceVersion: props.source?.source_version || '',
    sourceUri: props.source?.source_uri || '',
    licenseName: props.source?.license_name || '',
    isActive: props.source?.is_active ?? true
  })
}

watch(() => props.modelValue, (open) => {
  if (open) resetForm()
})

const submit = () => {
  if (!canSubmit.value || props.submitting) return
  const payload = {
    name: form.name,
    source_type: form.sourceType,
    source_version: form.sourceVersion,
    source_uri: form.sourceUri || null,
    license_name: form.licenseName || null
  }
  if (editing.value) payload.is_active = form.isActive
  emit('submit', payload)
}
</script>

<style scoped lang="scss">
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
