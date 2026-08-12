<template>
  <AuthLayout>
    <template #brand>
      <BrandPanel
        compact
        :logo-label="'CyberGuard'"
        :brand-title="'CyberGuard'"
        :tagline="'企业级安全运营与 DevSecOps 工作台'"
      />
    </template>

    <template #form>
      <div class="policy-view">
        <template v-if="loading">
          <el-skeleton :rows="6" animated />
        </template>

        <template v-else-if="error">
          <div class="policy-view__empty">
            <p class="policy-view__empty-title">{{ error }}</p>
            <router-link class="policy-view__back" to="/">
              <el-icon><ArrowLeft /></el-icon>
              返回首页
            </router-link>
          </div>
        </template>

        <template v-else-if="policy">
          <header class="policy-view__header">
            <p class="policy-view__eyebrow">CyberGuard · 政策文档</p>
            <h1 class="policy-view__title">{{ policy.title }}</h1>
            <p class="policy-view__meta">
              版本 {{ policy.version || '1.0' }} ·
              {{ formatDate(policy.updated_at) }} 更新
            </p>
          </header>

          <article class="policy-view__body">
            <MarkdownRenderer :content="policy.content" sanitize />
          </article>

          <footer class="policy-view__footer">
            <router-link class="policy-view__back" to="/">
              <el-icon><ArrowLeft /></el-icon>
              返回首页
            </router-link>
          </footer>
        </template>
      </div>
    </template>
  </AuthLayout>
</template>

<script setup>
import { ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ArrowLeft } from '@element-plus/icons-vue'
import { AuthLayout, BrandPanel } from '@/components/auth'
import MarkdownRenderer from '@/components/MarkdownRenderer.vue'
import { policyAPI } from '@/api'

const route = useRoute()

const loading = ref(false)
const error = ref('')
const policy = ref(null)

const TITLES = { terms: '用户协议', privacy: '隐私政策' }

function formatDate(value) {
  if (!value) return ''
  const date = new Date(value)
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

async function loadPolicy(slug) {
  loading.value = true
  error.value = ''
  policy.value = null
  try {
    const result = await policyAPI.get(slug)
    policy.value = result.policy
  } catch (e) {
    error.value = e.response?.status === 404 ? '该政策文档不存在' : '加载失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

watch(
  () => route.params.slug,
  (slug) => {
    if (slug) {
      document.title = `${TITLES[slug] || '政策文档'} - CyberGuard`
      loadPolicy(slug)
    }
  },
  { immediate: true }
)
</script>

<style lang="scss" scoped>
.policy-view {
  width: 100%;
  max-width: 720px;

  &__header {
    margin-bottom: 32px;
  }

  &__eyebrow {
    margin: 0 0 12px;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #9a9a92;
  }

  &__title {
    margin: 0 0 10px;
    font-size: clamp(28px, 4vw, 40px);
    font-weight: 800;
    letter-spacing: -0.02em;
    color: #1a1a1a;
  }

  &__meta {
    margin: 0;
    font-size: 13px;
    color: #9a9a92;
  }

  &__body {
    background: #fff;
    border-radius: 16px;
    padding: 4px 0;
  }

  &__footer {
    margin-top: 40px;
    padding-top: 24px;
    border-top: 1px solid #ececea;
  }

  &__back {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 14px;
    font-weight: 600;
    color: #6b6b6b;
    text-decoration: none;

    &:hover {
      color: #1a1a1a;
    }
  }

  &__empty {
    padding: 48px 0;
    text-align: center;
  }

  &__empty-title {
    margin: 0 0 20px;
    font-size: 16px;
    color: #9a9a92;
  }
}
</style>
