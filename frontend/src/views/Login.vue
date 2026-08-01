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
              <svg class="oauth-button__icon" viewBox="0 0 16 16" aria-hidden="true">
                <path
                  fill-rule="evenodd"
                  d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0 0 16 8c0-4.42-3.58-8-8-8z"
                />
              </svg>
              <span>GitHub 登录</span>
            </button>

            <button
              type="button"
              class="oauth-button oauth-button--google"
              @click="loginWithOAuth('google')"
            >
              <svg class="oauth-button__icon" viewBox="0 0 48 48" aria-hidden="true">
                <path
                  fill="#FFC107"
                  d="M43.611 20.083H42V20H24v8h11.303c-1.649 4.657-6.08 8-11.303 8-6.627 0-12-5.373-12-12s5.373-12 12-12c3.059 0 5.842 1.154 7.961 3.039l5.657-5.657C34.046 6.053 29.268 4 24 4 12.955 4 4 12.955 4 24s8.955 20 20 20 20-8.955 20-20c0-1.341-.138-2.65-.389-3.917z"
                />
                <path
                  fill="#FF3D00"
                  d="M6.306 14.691l6.571 4.819C14.655 15.108 18.961 12 24 12c3.059 0 5.842 1.154 7.961 3.039l5.657-5.657C34.046 6.053 29.268 4 24 4 16.318 4 9.656 8.337 6.306 14.691z"
                />
                <path
                  fill="#4CAF50"
                  d="M24 44c5.166 0 9.86-1.977 13.409-5.192l-6.19-5.238A11.91 11.91 0 0 1 24 36c-5.202 0-9.619-3.317-11.283-7.946l-6.522 5.025C9.505 39.556 16.227 44 24 44z"
                />
                <path
                  fill="#1976D2"
                  d="M43.611 20.083H42V20H24v8h11.303c-.792 2.237-2.231 4.166-4.087 5.571l6.19 5.238C36.971 39.205 44 34 44 24c0-1.341-.138-2.65-.389-3.917z"
                />
              </svg>
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
