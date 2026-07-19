<template>
  <div class="auth-page">
    <div class="auth-container">
      <div class="auth-card">
        <div class="auth-header">
          <el-icon :size="48" color="#2ea44f"><Shield /></el-icon>
          <h1>注册 CyberGuard</h1>
          <p>加入我们，开始学习之旅</p>
        </div>
        
        <el-form
          ref="formRef"
          :model="form"
          :rules="rules"
          class="auth-form"
          @submit.prevent="handleRegister"
        >
          <el-form-item prop="username">
            <el-input
              v-model="form.username"
              placeholder="请输入用户名"
              size="large"
              prefix-icon="User"
            >
              <template #append>
                <el-button @click="checkAvailable('username')">
                  {{ checking.username ? '检查中...' : '检查' }}
                </el-button>
              </template>
            </el-input>
          </el-form-item>
          
          <el-form-item prop="email">
            <el-input
              v-model="form.email"
              placeholder="请输入邮箱"
              size="large"
              prefix-icon="Message"
            >
              <template #append>
                <el-button @click="checkAvailable('email')">
                  {{ checking.email ? '检查中...' : '检查' }}
                </el-button>
              </template>
            </el-input>
          </el-form-item>
          
          <el-form-item prop="password">
            <el-input
              v-model="form.password"
              type="password"
              placeholder="请输入密码（至少6位）"
              size="large"
              prefix-icon="Lock"
              show-password
            />
          </el-form-item>
          
          <el-form-item prop="confirmPassword">
            <el-input
              v-model="form.confirmPassword"
              type="password"
              placeholder="请确认密码"
              size="large"
              prefix-icon="Lock"
              show-password
            />
          </el-form-item>
          
          <el-form-item prop="nickname">
            <el-input
              v-model="form.nickname"
              placeholder="请输入昵称（可选）"
              size="large"
              prefix-icon="UserFilled"
            />
          </el-form-item>
          
          <el-form-item>
            <el-button
              type="primary"
              size="large"
              :loading="loading"
              class="submit-btn"
              native-type="submit"
            >
              注册
            </el-button>
          </el-form-item>
        </el-form>
        
        <div class="auth-footer">
          <span>已有账号？</span>
          <router-link to="/login">立即登录</router-link>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { authAPI } from '@/api'
import { ElMessage } from 'element-plus'

const router = useRouter()
const userStore = useUserStore()

const formRef = ref()
const loading = ref(false)
const checking = reactive({ username: false, email: false })

const form = reactive({
  username: '',
  email: '',
  password: '',
  confirmPassword: '',
  nickname: ''
})

const validateConfirmPassword = (rule, value, callback) => {
  if (value !== form.password) {
    callback(new Error('两次输入的密码不一致'))
  } else {
    callback()
  }
}

const rules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 20, message: '用户名长度3-20个字符', trigger: 'blur' },
    { pattern: /^[a-zA-Z0-9_]+$/, message: '用户名只能包含字母、数字和下划线', trigger: 'blur' }
  ],
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '请输入有效的邮箱地址', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码至少6个字符', trigger: 'blur' }
  ],
  confirmPassword: [
    { required: true, message: '请确认密码', trigger: 'blur' },
    { validator: validateConfirmPassword, trigger: 'blur' }
  ]
}

const checkAvailable = async (field) => {
  const value = form[field]
  if (!value) {
    ElMessage.warning(`请先输入${field === 'username' ? '用户名' : '邮箱'}`)
    return
  }
  
  checking[field] = true
  try {
    const res = await authAPI.checkAvailable({ [field]: value })
    if (res.exists) {
      ElMessage.warning(`${field === 'username' ? '用户名' : '邮箱'}已被占用`)
    } else {
      ElMessage.success(`${field === 'username' ? '用户名' : '邮箱'}可用`)
    }
  } catch (error) {
    ElMessage.error('检查失败，请重试')
  } finally {
    checking[field] = false
  }
}

const handleRegister = async () => {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  
  loading.value = true
  const result = await userStore.register({
    username: form.username,
    email: form.email,
    password: form.password,
    nickname: form.nickname || form.username
  })
  loading.value = false
  
  if (result.success) {
    ElMessage.success('注册成功，请登录')
    router.push('/login')
  } else {
    ElMessage.error(result.error || '注册失败')
  }
}
</script>

<style lang="scss" scoped>
.auth-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f6f8fa;
  padding: 20px;
}

.auth-container {
  width: 100%;
  max-width: 420px;
}

.auth-card {
  background: #ffffff;
  border: 1px solid #d0d7de;
  border-radius: 6px;
  padding: 48px 40px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.auth-header {
  text-align: center;
  margin-bottom: 32px;
  
  h1 {
    font-size: 24px;
    color: #24292f;
    margin: 16px 0 8px;
    font-weight: 600;
  }
  
  p {
    color: #57606a;
    font-size: 14px;
  }
}

.auth-form {
  :deep(.el-form-item) {
    margin-bottom: 16px;
  }
  
  :deep(.el-input__wrapper) {
    border-radius: 6px;
  }
  
  :deep(.el-input-group__append) {
    border-radius: 0 6px 6px 0;
    background: #f6f8fa;
    border-color: #d0d7de;
    color: #57606a;
    
    .el-button {
      border: none;
      background: transparent;
      color: #2ea44f;
      font-weight: 500;
      
      &:hover {
        color: #2c974b;
      }
    }
  }
  
  .submit-btn {
    width: 100%;
    border-radius: 6px;
    font-weight: 500;
  }
}

.auth-footer {
  text-align: center;
  color: #57606a;
  font-size: 14px;
  margin-top: 8px;
  
  a {
    color: #2ea44f;
    margin-left: 4px;
    text-decoration: none;
    font-weight: 500;
    
    &:hover {
      text-decoration: underline;
    }
  }
}
</style>
