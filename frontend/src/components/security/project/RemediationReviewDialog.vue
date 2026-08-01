<template>
  <el-dialog v-model="visible" title="人工审核修复建议" width="520px" destroy-on-close @closed="resetForm">
    <el-alert type="warning" :closable="false" show-icon class="review-alert">审核只记录决策与评论；不会自动应用或执行 Diff。</el-alert>
    <el-form label-position="top" @submit.prevent="submit">
      <el-form-item label="审核决定" required>
        <el-radio-group v-model="form.reviewState">
          <el-radio label="accepted">接受</el-radio>
          <el-radio label="needs_revision">需要修改</el-radio>
          <el-radio label="rejected">拒绝</el-radio>
        </el-radio-group>
      </el-form-item>
      <el-form-item label="审核备注"><el-input v-model.trim="form.comment" type="textarea" :rows="4" maxlength="4000" show-word-limit placeholder="可选：记录验证范围、风险或后续要求。" /></el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="submit">提交审核</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, reactive, watch } from 'vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  suggestion: { type: Object, default: null },
  submitting: { type: Boolean, default: false }
})
const emit = defineEmits(['update:modelValue', 'submit'])
const form = reactive({ reviewState: 'accepted', comment: '' })
const visible = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value)
})

const resetForm = () => {
  form.reviewState = 'accepted'
  form.comment = ''
}

watch(() => [props.modelValue, props.suggestion], () => {
  if (!props.modelValue || !props.suggestion) return
  form.reviewState = props.suggestion.review_state === 'pending' ? 'accepted' : props.suggestion.review_state
  form.comment = props.suggestion.review_comment || ''
}, { immediate: true })

const submit = () => {
  if (!props.suggestion || props.submitting) return
  emit('submit', { reviewState: form.reviewState, comment: form.comment || null })
}
</script>

<style scoped lang="scss">
.review-alert { margin-bottom:16px; }
</style>
