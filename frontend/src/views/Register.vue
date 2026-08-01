<template>
  <AuthLayout>
    <template #brand>
      <BrandPanel />
    </template>

    <template #form>
      <AuthFormContainer title="创建账号" subtitle="注册 CyberGuard，开始你的安全工作台">
        <form class="auth-form" novalidate @submit.prevent="handleRegister">
          <FormInput
            v-model="form.username"
            label="用户名"
            placeholder="3-20 位字母、数字或下划线"
            :error="errors.username"
            autocomplete="username"
            @blur="checkAvailable('username')"
          />

          <FormInput
            v-model="form.email"
            type="email"
            label="邮箱"
            placeholder="请输入邮箱"
            :error="errors.email"
            autocomplete="email"
            @blur="checkAvailable('email')"
          />

          <PasswordInput
            v-model="form.password"
            label="密码"
            placeholder="至少 6 位"
            :error="errors.password"
            autocomplete="new-password"
          />

          <PasswordInput
            v-model="form.confirmPassword"
            label="确认密码"
            placeholder="请再次输入密码"
            :error="errors.confirmPassword"
            autocomplete="new-password"
          />

          <FormInput
            v-model="form.nickname"
            label="昵称（可选）"
            placeholder="请输入昵称"
            :error="errors.nickname"
          />

          <AgreementCheckbox v-model="agreed" :error="errors.agreed" />

          <SubmitButton :loading="submitting" text="注册" />

          <AuthFooter text="注册即表示您同意用户协议及隐私政策" />
          <AuthSwitchLink hint="已有账号？" action="立即登录" to="/login" />
        </form>
      </AuthFormContainer>
    </template>
  </AuthLayout>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { authAPI } from '@/api'
import { useUserStore } from '@/stores/user'
import { useAuthForm } from '@/composables/useAuthForm'
import {
  AuthLayout,
  BrandPanel,
  AuthFormContainer,
  FormInput,
  PasswordInput,
  SubmitButton,
  AgreementCheckbox,
  AuthFooter,
  AuthSwitchLink
} from '@/components/auth'

const router = useRouter()
const userStore = useUserStore()

const { form, errors, submitting, setError, clearError, clearErrors, run } = useAuthForm({
  username: '',
  email: '',
  password: '',
  confirmPassword: '',
  nickname: ''
})

const agreed = ref(false)
const checking = ref(false)

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
const USERNAME_PATTERN = /^[a-zA-Z0-9_]+$/

function validate() {
  clearErrors()
  let valid = true

  if (!form.username.trim()) {
    setError('username', '请输入用户名')
    valid = false
  } else if (form.username.trim().length < 3 || form.username.trim().length > 20) {
    setError('username', '用户名长度需在 3-20 个字符')
    valid = false
  } else if (!USERNAME_PATTERN.test(form.username.trim())) {
    setError('username', '用户名只能包含字母、数字和下划线')
    valid = false
  }

  if (!form.email.trim()) {
    setError('email', '请输入邮箱')
    valid = false
  } else if (!EMAIL_PATTERN.test(form.email.trim())) {
    setError('email', '请输入有效的邮箱地址')
    valid = false
  }

  if (!form.password) {
    setError('password', '请输入密码')
    valid = false
  } else if (form.password.length < 6) {
    setError('password', '密码至少 6 位')
    valid = false
  }

  if (!form.confirmPassword) {
    setError('confirmPassword', '请确认密码')
    valid = false
  } else if (form.password && form.confirmPassword !== form.password) {
    setError('confirmPassword', '两次输入的密码不一致')
    valid = false
  }

  if (!agreed.value) {
    setError('agreed', '请先阅读并同意用户协议及隐私政策')
    valid = false
  }

  return valid
}

async function checkAvailable(field) {
  const value = String(form[field] || '').trim()
  if (!value || checking.value) return

  checking.value = true
  try {
    const res = await authAPI.checkAvailable({ [field]: value })
    if (res.exists) {
      setError(field, field === 'username' ? '该用户名已被占用' : '该邮箱已被注册')
    } else {
      clearError(field)
    }
  } catch {
    // 检查失败不阻塞表单，交由提交时校验
  } finally {
    checking.value = false
  }
}

async function handleRegister() {
  if (!validate()) return

  await run(async () => {
    const result = await userStore.register({
      username: form.username.trim(),
      email: form.email.trim(),
      password: form.password,
      nickname: form.nickname.trim() || form.username.trim()
    })

    if (result.success) {
      ElMessage.success('注册成功，请登录')
      router.push('/login')
    } else {
      ElMessage.error(result.error || '注册失败')
    }
  })
}
</script>

<style lang="scss" scoped>
.auth-form {
  display: flex;
  flex-direction: column;
}
</style>
