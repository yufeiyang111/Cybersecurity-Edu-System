<template>
  <div class="oauth-card">
    <div class="oauth-card__desc">
      绑定后，下次可直接使用对应的第三方账号登录当前账号，无需再输密码。
    </div>

    <div v-for="p in providers" :key="p.key" class="oauth-card__item">
      <component :is="p.icon" :size="18" />
      <span class="oauth-card__name">{{ p.label }}</span>
      <el-tag v-if="isBound(p.key)" type="success" effect="plain">已绑定</el-tag>
      <el-tag v-else type="info" effect="plain">未绑定</el-tag>
      <el-button
        v-if="isBound(p.key)"
        size="small"
        type="danger"
        plain
        :loading="unbindingKey === p.key"
        @click="handleUnbind(p.key)"
      >
        解绑
      </el-button>
      <el-button
        v-else
        size="small"
        type="primary"
        plain
        :loading="bindingKey === p.key"
        @click="handleBind(p.key)"
      >
        绑定
      </el-button>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { authAPI } from '@/api'
import { ElMessage, ElMessageBox } from 'element-plus'
import { GithubIcon, GoogleIcon } from '@/components/icons'

const userStore = useUserStore()
const route = useRoute()
const router = useRouter()

const providers = [
  { key: 'github', label: 'GitHub', icon: GithubIcon },
  { key: 'google', label: 'Google', icon: GoogleIcon }
]
const bindingKey = ref('')
const unbindingKey = ref('')

const isBound = (key) => {
  const bindings = userStore.user?.oauth_bindings || []
  return bindings.some((b) => b.provider === key)
}

const handleBind = async (key) => {
  bindingKey.value = key
  try {
    const res = await authAPI.bindOAuth(key)
    if (!res?.url) {
      bindingKey.value = ''
      ElMessage.error('绑定失败：未获取到授权跳转地址')
      return
    }
    window.location.href = res.url
  } catch (error) {
    bindingKey.value = ''
    ElMessage.error(error.response?.data?.error || '发起绑定失败，请重试')
  }
}

const handleUnbind = async (key) => {
  const label = providers.find((p) => p.key === key)?.label || key
  try {
    await ElMessageBox.confirm(
      `确定要取消 ${label} 账号的绑定吗？取消后该第三方账号将无法直接登录本账号。如需同时撤销第三方平台的授权，请前往 ${label} 账号设置中移除「CyberGuard」的访问权限。`,
      '取消绑定',
      { type: 'warning', confirmButtonText: '取消绑定', cancelButtonText: '再想想' }
    )
  } catch {
    return
  }
  unbindingKey.value = key
  try {
    await authAPI.unbindOAuth(key)
    ElMessage.success(`已取消 ${label} 绑定`)
    await userStore.checkAuth()
  } catch (error) {
    ElMessage.error(error.response?.data?.error || '取消绑定失败，请重试')
  } finally {
    unbindingKey.value = ''
  }
}

watch(
  () => route.query.oauth_bind,
  async (val) => {
    if (val === 'ok') {
      ElMessage.success('第三方账号绑定成功')
      bindingKey.value = ''
      await userStore.checkAuth()
      router.replace({ query: { ...route.query, oauth_bind: undefined, provider: undefined } })
    }
  },
  { immediate: true }
)
</script>

<style lang="scss" scoped>
@use '@/styles/user-vars' as *;

.oauth-card {
  padding: 16px 20px;
  background: $bg-white;
  border: 1px solid $border-color;
  border-radius: 8px;
  box-shadow: $shadow-soft;

  &__desc {
    margin-bottom: 12px;
    font-size: 13px;
    color: $text-regular;
    line-height: 1.6;
  }

  &__item {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 0;
    border-bottom: 1px solid $border-lighter;

    &:last-child {
      border-bottom: none;
    }
  }

  &__name {
    flex: 1;
    font-weight: 500;
    color: $text-primary;
  }
}
</style>
