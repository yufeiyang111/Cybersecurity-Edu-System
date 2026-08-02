<template>
  <AuthLayout>
    <template #brand>
      <BrandPanel />
    </template>

    <template #form>
      <AuthFormContainer title="第三方登录">
        <div class="oauth-status">
          <div v-if="!hasError" class="status-spinner" aria-hidden="true"></div>
          <p class="status-text" :class="{ 'is-error': hasError }">{{ statusText }}</p>
          <el-button v-if="hasError" type="primary" round @click="goBack">{{ backText }}</el-button>
        </div>
      </AuthFormContainer>
    </template>
  </AuthLayout>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'
import { AuthLayout, BrandPanel, AuthFormContainer } from '@/components/auth'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const statusText = ref('正在处理登录，请稍候...')
const hasError = ref(false)
const backText = ref('返回登录')

onMounted(async () => {
  const { token, error } = route.query

  if (error) {
    hasError.value = true
    statusText.value = decodeURIComponent(error)
    backText.value = userStore.isLoggedIn ? '返回个人中心' : '返回登录'
    return
  }

  if (!token) {
    hasError.value = true
    statusText.value = '登录回调缺少凭证，请重新登录'
    backText.value = userStore.isLoggedIn ? '返回个人中心' : '返回登录'
    return
  }

  userStore.token = token
  localStorage.setItem('token', token)

  const ok = await userStore.checkAuth()
  if (ok) {
    ElMessage.success('登录成功')
    router.replace('/')
  } else {
    hasError.value = true
    statusText.value = '登录状态校验失败，请重试'
  }
})

function goBack() {
  if (userStore.isLoggedIn) {
    router.replace('/user/profile')
  } else {
    router.replace('/login')
  }
}
</script>

<style lang="scss" scoped>
.oauth-status {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  padding: 24px 0;
}

.status-spinner {
  width: 32px;
  height: 32px;
  border: 3px solid rgba(0, 0, 0, 0.1);
  border-top-color: var(--el-color-primary);
  border-radius: 50%;
  animation: oauth-spin 0.8s linear infinite;
}

.status-text {
  margin: 0;
  color: var(--el-text-color-primary);
  font-size: 14px;

  &.is-error {
    color: var(--el-color-danger);
  }
}

@keyframes oauth-spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
