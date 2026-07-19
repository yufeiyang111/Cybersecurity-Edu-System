<template>
  <div class="profile-page">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>个人信息</span>
        </div>
      </template>

      <div class="avatar-section">
        <el-avatar :size="80" :src="form.avatar_url || undefined">
          {{ form.nickname?.[0] || form.username?.[0] || '用户' }}
        </el-avatar>
        <div class="avatar-actions">
          <el-upload
            :show-file-list="false"
            :before-upload="handleAvatarBeforeUpload"
            :http-request="handleAvatarUpload"
            accept="image/*"
          >
            <el-button size="small" type="primary">更换头像</el-button>
          </el-upload>
          <span class="avatar-tip">支持 JPG、PNG 格式，建议 200x200 像素</span>
        </div>
      </div>

      <el-divider />

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-width="100px"
      >
        <el-form-item label="用户名">
          <el-input v-model="form.username" disabled />
        </el-form-item>

        <el-form-item label="邮箱" prop="email">
          <el-input v-model="form.email" />
        </el-form-item>

        <el-form-item label="昵称" prop="nickname">
          <el-input v-model="form.nickname" placeholder="请输入昵称" />
        </el-form-item>

        <el-form-item label="角色">
          <el-tag>{{ getRoleText(userStore.user?.role) }}</el-tag>
        </el-form-item>

        <el-form-item label="注册时间">
          <span>{{ formatDate(userStore.user?.created_at) }}</span>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" @click="handleUpdateProfile" :loading="loading">
            保存修改
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card class="mt-16">
      <template #header>
        <div class="card-header">
          <span>修改密码</span>
        </div>
      </template>

      <el-form
        ref="passwordFormRef"
        :model="passwordForm"
        :rules="passwordRules"
        label-width="100px"
      >
        <el-form-item label="旧密码" prop="oldPassword">
          <el-input v-model="passwordForm.oldPassword" type="password" show-password />
        </el-form-item>

        <el-form-item label="新密码" prop="newPassword">
          <el-input v-model="passwordForm.newPassword" type="password" show-password />
        </el-form-item>

        <el-form-item label="确认密码" prop="confirmPassword">
          <el-input v-model="passwordForm.confirmPassword" type="password" show-password />
        </el-form-item>

        <el-form-item>
          <el-button type="primary" @click="handleChangePassword" :loading="passwordLoading">
            修改密码
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useUserStore } from '@/stores/user'
import { ElMessage } from 'element-plus'

const userStore = useUserStore()
const formRef = ref()
const passwordFormRef = ref()
const loading = ref(false)
const passwordLoading = ref(false)

const form = reactive({
  username: '',
  email: '',
  nickname: '',
  avatar_url: ''
})

const passwordForm = reactive({
  oldPassword: '',
  newPassword: '',
  confirmPassword: ''
})

const validateConfirmPassword = (rule, value, callback) => {
  if (value !== passwordForm.newPassword) {
    callback(new Error('两次输入的密码不一致'))
  } else {
    callback()
  }
}

const rules = {
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '请输入有效的邮箱地址', trigger: 'blur' }
  ],
  nickname: [
    { min: 2, max: 20, message: '昵称长度2-20个字符', trigger: 'blur' }
  ]
}

const passwordRules = {
  oldPassword: [
    { required: true, message: '请输入旧密码', trigger: 'blur' }
  ],
  newPassword: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, message: '密码至少6个字符', trigger: 'blur' }
  ],
  confirmPassword: [
    { required: true, message: '请确认密码', trigger: 'blur' },
    { validator: validateConfirmPassword, trigger: 'blur' }
  ]
}

const getRoleText = (role) => {
  const texts = {
    admin: '管理员',
    teacher: '教师',
    user: '普通用户',
    guest: '游客'
  }
  return texts[role] || role
}

const formatDate = (dateStr) => {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleString('zh-CN')
}

const handleUpdateProfile = async () => {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  const result = await userStore.updateProfile({
    email: form.email,
    nickname: form.nickname,
    avatar_url: form.avatar_url
  })
  loading.value = false

  if (result.success) {
    ElMessage.success('个人信息更新成功')
  } else {
    ElMessage.error(result.error || '更新失败')
  }
}

const handleAvatarBeforeUpload = (file) => {
  const isImage = file.type.startsWith('image/')
  const isLt2M = file.size / 1024 / 1024 < 2

  if (!isImage) {
    ElMessage.error('只能上传图片文件')
    return false
  }
  if (!isLt2M) {
    ElMessage.error('图片大小不能超过 2MB')
    return false
  }
  return true
}

const handleAvatarUpload = async ({ file }) => {
  // 简单实现：使用 Base64 编码上传
  const reader = new FileReader()
  reader.onload = async (e) => {
    const avatarUrl = e.target.result
    form.avatar_url = avatarUrl

    // 自动保存
    loading.value = true
    const result = await userStore.updateProfile({
      email: form.email,
      nickname: form.nickname,
      avatar_url: avatarUrl
    })
    loading.value = false

    if (result.success) {
      ElMessage.success('头像更新成功')
    } else {
      ElMessage.error(result.error || '头像更新失败')
    }
  }
  reader.readAsDataURL(file)
}

const handleChangePassword = async () => {
  const valid = await passwordFormRef.value.validate().catch(() => false)
  if (!valid) return

  passwordLoading.value = true
  const result = await userStore.changePassword(
    passwordForm.oldPassword,
    passwordForm.newPassword
  )
  passwordLoading.value = false

  if (result.success) {
    ElMessage.success('密码修改成功')
    passwordForm.oldPassword = ''
    passwordForm.newPassword = ''
    passwordForm.confirmPassword = ''
    passwordFormRef.value.resetFields()
  } else {
    ElMessage.error(result.error || '修改失败')
  }
}

onMounted(() => {
  if (userStore.user) {
    form.username = userStore.user.username || ''
    form.email = userStore.user.email || ''
    form.nickname = userStore.user.nickname || ''
    form.avatar_url = userStore.user.avatar_url || ''
  }
})
</script>

<style lang="scss" scoped>
.profile-page {
  :deep(.el-card) {
    max-width: 600px;
  }

  .mt-16 {
    margin-top: 24px;
  }

  .card-header {
    font-weight: 600;
  }

  .avatar-section {
    display: flex;
    align-items: center;
    gap: 24px;
    padding: 16px 0;

    .avatar-actions {
      display: flex;
      flex-direction: column;
      gap: 8px;

      .avatar-tip {
        font-size: 12px;
        color: #909399;
      }
    }
  }
}
</style>
