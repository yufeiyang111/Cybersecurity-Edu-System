<template>
  <el-dialog v-model="visible" :title="provider ? '编辑 LLM 配置' : '添加 LLM 配置'" width="min(520px, calc(100vw - 32px))" destroy-on-close @closed="reset">
    <el-form label-position="top" @submit.prevent="submit">
      <el-form-item label="配置名称" required><el-input v-model.trim="form.name" maxlength="100" placeholder="例如 private-qwen" /></el-form-item>
      <el-form-item label="API 地址" required><el-input v-model.trim="form.base_url" placeholder="https://llm.example/v1" /></el-form-item>
      <el-form-item label="模型名称" required><el-input v-model.trim="form.model" maxlength="200" placeholder="qwen2.5-72b-instruct" /></el-form-item>
      <el-form-item label="最大输出 Tokens（可选）"><el-input v-model.number="form.max_tokens" type="number" min="1" :max="1000000" placeholder="默认 2048；推理模型（如 deepseek）建议 8192，上限 1M" /></el-form-item>
      <el-form-item label="API Key" :required="!provider"><el-input v-model="form.api_key" type="password" show-password :placeholder="provider ? '留空以保留现有密钥' : '输入私有服务 API Key'" /></el-form-item>
      <div class="form-switches"><el-switch v-model="form.is_enabled" active-text="启用配置" /><el-switch v-model="form.is_default" active-text="设为默认" /></div>
    </el-form>
    <template #footer><BaseButton @click="visible = false">取消</BaseButton><BaseButton variant="primary" :disabled="submitting" @click="submit">{{ submitting ? '保存中...' : '保存配置' }}</BaseButton></template>
  </el-dialog>
</template>

<script setup>
import { computed, reactive, watch } from 'vue'
import { BaseButton } from '@/components/ui'

const props = defineProps({ modelValue: { type: Boolean, default: false }, provider: { type: Object, default: null }, submitting: { type: Boolean, default: false } })
const emit = defineEmits(['update:modelValue', 'submit'])
const visible = computed({ get: () => props.modelValue, set: (value) => emit('update:modelValue', value) })
const form = reactive({ name: '', base_url: '', model: '', api_key: '', is_enabled: true, is_default: false, max_tokens: null })

watch(() => props.provider, (provider) => {
  Object.assign(form, provider ? { name: provider.name, base_url: provider.base_url, model: provider.model, api_key: '', is_enabled: provider.is_enabled, is_default: provider.is_default, max_tokens: provider.max_tokens ?? null } : { name: '', base_url: '', model: '', api_key: '', is_enabled: true, is_default: false, max_tokens: null })
}, { immediate: true })
const reset = () => { Object.assign(form, { name: '', base_url: '', model: '', api_key: '', is_enabled: true, is_default: false, max_tokens: null }) }
const submit = () => emit('submit', { ...form, max_tokens: form.max_tokens || null })
</script>

<style scoped lang="scss">
.form-switches { display: flex; gap: 24px; padding-top: 2px; }
</style>
