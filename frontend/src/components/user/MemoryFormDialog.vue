<template>
  <el-dialog
    :model-value="modelValue"
    :title="memory ? '编辑记忆' : '新增记忆'"
    width="min(560px, calc(100vw - 32px))"
    destroy-on-close
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <el-form label-position="top">
      <el-form-item label="内容">
        <el-input
          v-model="form.content"
          type="textarea"
          :rows="4"
          maxlength="2000"
          show-word-limit
          placeholder="例如：用户负责公司安全运营，重点关注 Web 安全"
        />
      </el-form-item>
      <el-form-item label="分类">
        <el-select v-model="form.category" class="memory-form__category">
          <el-option
            v-for="option in categories"
            :key="option.value"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="$emit('update:modelValue', false)">取消</el-button>
      <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { memoryAPI } from '@/api'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  memory: { type: Object, default: null }
})
const emit = defineEmits(['update:modelValue', 'saved'])

const categories = [
  { value: 'preference', label: '偏好' },
  { value: 'fact', label: '事实' },
  { value: 'decision', label: '决定' },
  { value: 'goal', label: '目标' },
  { value: 'other', label: '其他' }
]

const form = ref({ content: '', category: 'fact' })
const saving = ref(false)

watch(
  () => props.modelValue,
  (open) => {
    if (!open) return
    form.value = {
      content: props.memory?.content || '',
      category: props.memory?.category || 'fact'
    }
  }
)

const handleSave = async () => {
  const content = form.value.content.trim()
  if (!content) {
    ElMessage.warning('请输入记忆内容')
    return
  }
  saving.value = true
  try {
    if (props.memory) {
      await memoryAPI.update(props.memory.id, {
        content,
        category: form.value.category
      })
    } else {
      await memoryAPI.create({
        content,
        category: form.value.category
      })
    }
    ElMessage.success(props.memory ? '记忆已更新' : '记忆已添加')
    emit('update:modelValue', false)
    emit('saved')
  } catch (e) {
    ElMessage.error(e?.response?.data?.error || '保存失败')
  } finally {
    saving.value = false
  }
}
</script>

<style lang="scss" scoped>
.memory-form__category {
  width: 100%;
}
</style>
