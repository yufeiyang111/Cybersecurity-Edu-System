<template>
  <div class="help-center">
    <header class="help-topbar">
      <div class="help-topbar__inner">
        <router-link to="/" class="help-topbar__brand">
          <span class="help-topbar__logo">
            <BaseIcon name="book" :size="18" />
          </span>
          <span class="help-topbar__name">帮助中心</span>
        </router-link>
        <nav class="help-topbar__crumbs">
          <router-link to="/help" class="help-topbar__crumb">文档</router-link>
          <template v-if="activeSlug && currentDocument">
            <BaseIcon name="chevron-down" :size="12" class="help-topbar__sep" />
            <span class="help-topbar__crumb help-topbar__crumb--current">
              {{ currentDocument.title }}
            </span>
          </template>
        </nav>
        <button type="button" class="help-topbar__back" @click="$router.push('/qa')">
          <BaseIcon name="arrow-left" :size="14" />
          <span>返回问答</span>
        </button>
      </div>
    </header>

    <div class="help-layout">
      <HelpSidebar
        :tree="tree"
        :active-slug="activeSlug"
        :loading="loading"
        @select-document="selectDocument"
      />

      <main class="help-main">
        <div v-if="documentLoading" class="help-skeleton">
          <div class="skeleton-line w-40"></div>
          <div class="skeleton-line title"></div>
          <div class="skeleton-line w-70"></div>
          <div class="skeleton-line w-95"></div>
          <div class="skeleton-line w-85"></div>
          <div class="skeleton-line w-90"></div>
        </div>

        <template v-else-if="currentDocument">
          <HelpDocument
            :document="currentDocument"
            :prev-document="prevDocument"
            :next-document="nextDocument"
            @select-document="selectDocument"
          />
        </template>

        <HelpHome
          v-else-if="!errorMessage"
          :tree="tree"
          :loading="loading"
          @select-document="selectDocument"
        />

        <div v-else class="help-error">{{ errorMessage }}</div>
      </main>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { BaseIcon } from '@/components/ui'
import HelpSidebar from '@/components/help/HelpSidebar.vue'
import HelpDocument from '@/components/help/HelpDocument.vue'
import HelpHome from '@/components/help/HelpHome.vue'
import { useHelpCenter } from '@/composables/security/useHelpCenter'

const route = useRoute()
const activeSlug = ref('')
const { loading, documentLoading, errorMessage, tree, currentDocument, loadTree, loadDocument } = useHelpCenter()

const activeSlugFromRoute = computed(() => route.params.slug || '')

watch(
  activeSlugFromRoute,
  (slug) => {
    if (!slug) {
      activeSlug.value = ''
      return
    }
    activeSlug.value = slug
    loadDocument(slug)
  },
  { immediate: true }
)

const selectDocument = (slug) => {
  if (slug === activeSlug.value) return
  activeSlug.value = slug
  loadDocument(slug)
}

// 扁平化所有文档（含分类路径），用于上一篇/下一篇导航
const flatDocs = computed(() => {
  const items = []
  const walk = (nodes) => {
    for (const node of nodes) {
      for (const doc of node.documents || []) {
        items.push({ ...doc, categoryName: node.name })
      }
      walk(node.children || [])
    }
  }
  walk(tree.value)
  return items
})

const currentIndex = computed(() =>
  flatDocs.value.findIndex((doc) => doc.slug === activeSlug.value)
)

const prevDocument = computed(() => {
  const index = currentIndex.value
  if (index <= 0) return null
  return flatDocs.value[index - 1]
})

const nextDocument = computed(() => {
  const index = currentIndex.value
  if (index < 0 || index >= flatDocs.value.length - 1) return null
  return flatDocs.value[index + 1]
})

loadTree()
</script>

<style scoped lang="scss">
.help-center {
  min-height: 100vh;
  background: var(--chat-canvas);
  color: var(--chat-ink);
}

.help-topbar {
  position: sticky;
  top: 0;
  z-index: 100;
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(8px);
  border-bottom: 1px solid var(--chat-hairline);
  animation: topbar-slide-down 0.3s ease both;

  @keyframes topbar-slide-down {
    from {
      opacity: 0;
      transform: translateY(-100%);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  &__inner {
    max-width: 1440px;
    margin: 0 auto;
    height: 56px;
    padding: 0 24px;
    display: flex;
    align-items: center;
    gap: 20px;
  }

  &__brand {
    display: flex;
    align-items: center;
    gap: 8px;
    text-decoration: none;
  }

  &__logo {
    width: 30px;
    height: 30px;
    border-radius: 8px;
    background: var(--chat-accent);
    color: var(--chat-canvas);
    display: flex;
    align-items: center;
    justify-content: center;
  }

  &__name {
    font-size: 15px;
    font-weight: 700;
    color: var(--chat-ink);
  }

  &__crumbs {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 13px;
    color: var(--chat-hollow);
  }

  &__crumb {
    text-decoration: none;
    color: var(--chat-hollow);

    &:hover {
      color: var(--chat-ink);
    }

    &--current {
      color: var(--chat-ink);
      font-weight: 500;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      max-width: 360px;
    }
  }

  &__sep {
    transform: rotate(-90deg);
    color: var(--chat-hairline-strong);
  }

  &__back {
    margin-left: auto;
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 6px 12px;
    border: 1px solid var(--chat-hairline-strong);
    border-radius: var(--chat-radius);
    background: var(--chat-field);
    color: var(--chat-muted);
    font-size: 13px;
    cursor: pointer;
    text-decoration: none;

    &:hover {
      background: var(--chat-hover);
      border-color: var(--chat-hairline-strong);
    }
  }
}

.help-layout {
  display: flex;
  max-width: 1440px;
  margin: 0 auto;
  min-height: calc(100vh - 56px);
}

.help-main {
  flex: 1;
  min-width: 0;
  padding: 40px 48px 80px;
  animation: main-fade-in 0.35s ease both;

  @keyframes main-fade-in {
    from {
      opacity: 0;
    }
    to {
      opacity: 1;
    }
  }
}

@media (prefers-reduced-motion: reduce) {
  .help-topbar,
  .help-main {
    animation: none;
  }
}

.help-skeleton {
  max-width: 760px;

  .skeleton-line {
    height: 16px;
    border-radius: 4px;
    background: linear-gradient(90deg, var(--chat-hover) 25%, var(--chat-hairline) 50%, var(--chat-hover) 75%);
    background-size: 200% 100%;
    animation: shimmer 1.2s infinite;
    margin-bottom: 14px;

    &.title {
      height: 32px;
      width: 70%;
      margin-bottom: 20px;
    }

    &.w-40 { width: 40%; }
    &.w-70 { width: 70%; }
    &.w-85 { width: 85%; }
    &.w-90 { width: 90%; }
    &.w-95 { width: 95%; }
  }
}

@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

.help-error {
  padding: 60px 24px;
  color: var(--chat-danger-ink);
  font-size: 14px;
  text-align: center;
}

@media (max-width: 1024px) {
  .help-main {
    padding: 24px 20px 60px;
  }
}

@media (max-width: 768px) {
  .help-topbar__inner {
    padding: 0 16px;
  }

  .help-topbar__crumbs {
    display: none;
  }
}
</style>