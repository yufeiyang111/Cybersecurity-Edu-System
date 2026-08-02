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

          <div class="oauth-divider">
            <span class="oauth-divider__line" aria-hidden="true"></span>
            <span class="oauth-divider__text">或使用第三方账号登录</span>
            <span class="oauth-divider__line" aria-hidden="true"></span>
          </div>

          <div class="oauth-buttons">
            <button
              type="button"
              class="oauth-button oauth-button--github"
              @click="loginWithOAuth('github')"
            >
              <ProviderIcon provider="github" class="oauth-button__icon" />
              <span>GitHub 登录</span>
            </button>

            <button
              type="button"
              class="oauth-button oauth-button--google"
              @click="loginWithOAuth('google')"
            >
              <ProviderIcon provider="google" class="oauth-button__icon" />
              <span>Google 登录</span>
            </button>
          </div>

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
import ProviderIcon from '@/components/ProviderIcon.vue'

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

function loginWithOAuth(provider) {
  window.location.href = `/api/auth/oauth/${provider}/authorize`
}
</script>

<style lang="scss" scoped>
.auth-form {
  display: flex;
  flex-direction: column;
}

.oauth-divider {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 22px 0 16px;

  &__line {
    flex: 1;
    height: 1px;
    background: #e6e6e0;
  }

  &__text {
    flex-shrink: 0;
    font-size: 12px;
    color: #9a9a92;
  }
}

.oauth-buttons {
  display: flex;
  gap: 12px;
  margin-bottom: 4px;
}

.oauth-button {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  flex: 1;
  padding: 13px 12px;
  font-size: 14px;
  font-weight: 600;
  font-family: inherit;
  border-radius: 14px;
  cursor: pointer;
  transition: background 0.2s ease, transform 0.1s ease;

  &:active {
    transform: translateY(1px);
  }

  &__icon {
    width: 18px;
    height: 18px;
  }

  &--github {
    color: #1a1a1a;
    background: #ffffff;
    border: 1px solid #d9d9d3;

    &:hover {
      background: #f7f7f5;
    }
  }

  &--google {
    color: #1a1a1a;
    background: #ffffff;
    border: 1px solid #d9d9d3;

    &:hover {
      background: #f7f7f5;
    }
  }
}
</style>
