<template>
  <el-dialog v-model="visible" title="新增安全知识源" width="560px" destroy-on-close @closed="resetForm">
    <el-form label-position="top" @submit.prevent="submit">
      <el-form-item label="来源名称" required><el-input v-model.trim="form.name" maxlength="255" placeholder="例如 OWASP ASVS" /></el-form-item>
      <div class="form-grid">
        <el-form-item label="来源类型" required><el-input v-model.trim="form.sourceType" maxlength="64" placeholder="standard / internal / advisory" /></el-form-item>
        <el-form-item label="来源版本" required><el-input v-model.trim="form.sourceVersion" maxlength="255" placeholder="例如 5.0" /></el-form-item>
      </div>
      <el-form-item label="来源地址"><el-input v-model.trim="form.sourceUri" maxlength="2048" placeholder="可选：不含查询参数的 HTTPS 地址" /></el-form-item>
      <el-form-item label="许可证"><el-input v-model.trim="form.licenseName" maxlength="255" placeholder="可选：例如 CC BY-SA 4.0" /></el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" :disabled="!canSubmit" @click="submit">创建来源</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, reactive } from 'vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  submitting: { type: Boolean, default: false }
})
const emit = defineEmits(['update:modelValue', 'submit'])
const form = reactive({ name: '', sourceType: 'standard', sourceVersion: '', sourceUri: '', licenseName: '' })
const visible = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value)
})
const canSubmit = computed(() => Boolean(form.name && form.sourceType && form.sourceVersion))

const resetForm = () => Object.assign(form, { name: '', sourceType: 'standard', sourceVersion: '', sourceUri: '', licenseName: '' })
const submit = () => {
  if (!canSubmit.value || props.submitting) return
  emit('submit', {
    name: form.name,
    source_type: form.sourceType,
    source_version: form.sourceVersion,
    source_uri: form.sourceUri || null,
    license_name: form.licenseName || null
  })
}
</script>

<style scoped lang="scss">
.form-grid { display:grid; grid-template-columns:1fr; gap:14px; }
@media(min-width:560px){ .form-grid{grid-template-columns:1fr 1fr} }
</style>
