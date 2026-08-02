<template>
  <el-dialog
    :model-value="modelValue"
    title="编辑个人资料"
    width="480px"
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
      <el-form-item label="昵称" prop="nickname">
        <el-input v-model="form.nickname" placeholder="请输入昵称" />
      </el-form-item>
      <el-form-item label="邮箱" prop="email">
        <el-input v-model="form.email" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="$emit('update:modelValue', false)">取消</el-button>
      <el-button type="primary" :loading="loading" @click="handleSubmit">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'

const props = defineProps({
  modelValue: { type: Boolean, default: false }
})
const emit = defineEmits(['update:modelValue', 'success'])

const userStore = useUserStore()
const formRef = ref()
const loading = ref(false)

const form = reactive({
  email: '',
  nickname: ''
})

const rules = {
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '请输入有效的邮箱地址', trigger: 'blur' }
  ],
  nickname: [
    { min: 2, max: 20, message: '昵称长度2-20个字符', trigger: 'blur' }
  ]
}

watch(
  () => props.modelValue,
  (val) => {
    if (val) {
      form.email = userStore.user?.email || ''
      form.nickname = userStore.user?.nickname || ''
      formRef.value?.clearValidate()
    }
  }
)

const handleSubmit = async () => {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  const result = await userStore.updateProfile({
    email: form.email,
    nickname: form.nickname,
    avatar_url: userStore.user?.avatar_url || ''
  })
  loading.value = false

  if (result.success) {
    ElMessage.success('个人信息更新成功')
    emit('success')
    emit('update:modelValue', false)
  } else {
    ElMessage.error(result.error || '更新失败')
  }
}
</script>
