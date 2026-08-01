<template>
  <AuthLayout>
    <template #brand>
      <BrandPanel />
    </template>

    <template #form>
      <AuthFormContainer title="欢迎回来" subtitle="登录 CyberGuard，继续你的安全运营工作">
        <form class="auth-form" novalidate @submit.prevent="handleLogin">
          <FormInput
            v-model="form.username"
            label="用户名"
            placeholder="请输入用户名"
            :error="errors.username"
            autocomplete="username"
          />

          <PasswordInput
            v-model="form.password"
            label="密码"
            placeholder="请输入密码"
            :error="errors.password"
            autocomplete="current-password"
            :show-forgot="true"
            @forgot="handleForgotPassword"
          />

          <SubmitButton :loading="submitting" text="登录" />

          <AuthFooter />
          <AuthSwitchLink hint="还没有账号？" action="立即注册" to="/register" />
        </form>
      </AuthFormContainer>
    </template>
  </AuthLayout>
</template>

<script setup>
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'
import { useAuthForm } from '@/composables/useAuthForm'
import {
  AuthLayout,
  BrandPanel,
  AuthFormContainer,
  FormInput,
  PasswordInput,
  SubmitButton,
  AuthFooter,
  AuthSwitchLink
} from '@/components/auth'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

const { form, errors, submitting, setError, clearErrors, run } = useAuthForm({
  username: '',
  password: ''
})

function validate() {
  clearErrors()
  let valid = true

  if (!form.username.trim()) {
    setError('username', '请输入用户名')
    valid = false
  }

  if (!form.password) {
    setError('password', '请输入密码')
    valid = false
  } else if (form.password.length < 6) {
    setError('password', '密码至少 6 位')
    valid = false
  }

  return valid
}

function handleForgotPassword() {
  ElMessage.info('请联系管理员重置密码')
}

async function handleLogin() {
  if (!validate()) return

  await run(async () => {
    const result = await userStore.login(form.username.trim(), form.password)
    if (result.success) {
      ElMessage.success('登录成功')
      const redirect = route.query.redirect || '/'
      router.push(redirect)
    } else {
      ElMessage.error(result.error || '登录失败')
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
