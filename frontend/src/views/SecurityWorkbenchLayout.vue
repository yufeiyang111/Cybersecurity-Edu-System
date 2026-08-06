<template>
  <div class="wb-shell">
    <header class="topbar">
      <button class="mobile-menu-btn" type="button" title="打开导航" @click="mobileSidebarOpen = true">
        <el-icon><Menu /></el-icon>
      </button>
      <div class="brand" @click="router.push('/')">
        <span class="brand-logo">CG</span>
        <span class="brand-name">CodeGuard</span>
        <span class="brand-sub">代码安全工作台</span>
      </div>

      <nav class="top-nav">
        <router-link class="top-nav__item top-nav__item--active" to="/security/projects">漏洞扫描</router-link>
        <span class="top-nav__item top-nav__item--disabled" title="即将上线">依赖分析</span>
        <span class="top-nav__item top-nav__item--disabled" title="即将上线">代码审计</span>
        <span class="top-nav__item top-nav__item--disabled" title="即将上线">合规检查</span>
        <router-link class="top-nav__item" to="/security/knowledge">知识库</router-link>
      </nav>

      <div class="top-actions">
        <el-button class="btn-doc" plain :icon="DocumentIcon" @click="onDocClick">文档</el-button>
        <el-button class="btn-gh" :icon="GithubIcon" @click="goWithQuery('import')">GitHub 导入</el-button>
        <el-button type="primary" :icon="PlusIcon" @click="goWithQuery('new')">新建项目</el-button>
        <el-dropdown trigger="click" @command="handleCommand">
          <span class="user-trigger">
            <el-avatar class="user-avatar" :size="32" :src="userStore.user?.avatar_url || undefined">
              {{ avatarText }}
            </el-avatar>
            <span class="user-name">{{ displayName }}</span>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="profile">个人中心</el-dropdown-item>
              <el-dropdown-item command="logout" divided>退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </header>

    <div class="wb-body">
      <aside class="sidebar" :class="{ 'sidebar--open': mobileSidebarOpen }">
        <div class="side-group">
          <p class="side-title">工作台</p>
          <router-link class="side-item" :class="{ 'side-item--active': route.path.startsWith('/security/projects') }" to="/security/projects">
            <el-icon><Grid /></el-icon><span>项目总览</span>
          </router-link>
          <router-link
            class="side-item side-item--agent"
            :class="{ 'side-item--active': route.path.includes('/agent') }"
            to="/security/agent"
          >
            <el-icon><Promotion /></el-icon><span>Agent 工作台</span>
          </router-link>
          <router-link class="side-item" :class="{ 'side-item--active': route.path.startsWith('/security/knowledge') }" to="/security/knowledge">
            <el-icon><Collection /></el-icon><span>知识库</span>
          </router-link>
          <span class="side-item side-item--disabled" title="即将上线">
            <el-icon><Warning /></el-icon><span>漏洞库</span>
            <span v-if="vulnBadge > 0" class="side-badge">{{ vulnBadge }}</span>
          </span>
          <span class="side-item side-item--disabled" title="即将上线">
            <el-icon><Document /></el-icon><span>扫描报告</span>
          </span>
        </div>

        <div class="side-group">
          <p class="side-title">模型运营</p>
          <router-link class="side-item" :class="{ 'side-item--active': route.path.startsWith('/security/llm/providers') }" to="/security/llm/providers" @click="mobileSidebarOpen = false">
            <el-icon><Monitor /></el-icon><span>LLM 配置</span>
          </router-link>
          <router-link class="side-item" :class="{ 'side-item--active': route.path.startsWith('/security/llm/logs') }" to="/security/llm/logs" @click="mobileSidebarOpen = false">
            <el-icon><List /></el-icon><span>用量日志</span>
          </router-link>
          <router-link class="side-item" :class="{ 'side-item--active': route.path.startsWith('/security/llm/analytics') }" to="/security/llm/analytics" @click="mobileSidebarOpen = false">
            <el-icon><DataLine /></el-icon><span>模型调用分析</span>
          </router-link>
        </div>

        <div class="side-group">
          <p class="side-title">安全能力</p>
          <span class="side-item side-item--disabled" title="即将上线">
            <el-icon><Monitor /></el-icon><span>SAST 静态分析</span>
          </span>
          <span class="side-item side-item--disabled" title="即将上线">
            <el-icon><Box /></el-icon><span>SCA 依赖检测</span>
          </span>
          <span class="side-item side-item--disabled" title="即将上线">
            <el-icon><Key /></el-icon><span>密钥泄露检测</span>
          </span>
          <span class="side-item side-item--disabled" title="即将上线">
            <el-icon><DataLine /></el-icon><span>单元测试覆盖</span>
          </span>
        </div>

        <div class="side-group">
          <p class="side-title">系统</p>
          <span class="side-item side-item--disabled" title="即将上线">
            <el-icon><Setting /></el-icon><span>规则配置</span>
          </span>
          <span class="side-item side-item--disabled" title="即将上线">
            <el-icon><User /></el-icon><span>团队管理</span>
          </span>
          <span class="side-item side-item--disabled" title="即将上线">
            <el-icon><List /></el-icon><span>操作日志</span>
          </span>
        </div>
      </aside>
      <button v-if="mobileSidebarOpen" class="sidebar-backdrop" type="button" aria-label="关闭导航" @click="mobileSidebarOpen = false" />

      <main class="wb-main">
        <router-view />
      </main>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Box, Collection, DataLine, Document, Grid, Key, List, Menu, Monitor, Promotion, Setting, User, Warning } from '@element-plus/icons-vue'
import { securityAPI } from '@/api'
import { useUserStore } from '@/stores/user'
import { DocumentIcon, GithubIcon, PlusIcon } from '@/components/icons'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()
const vulnBadge = ref(0)
const mobileSidebarOpen = ref(false)

const displayName = computed(() => userStore.user?.nickname || userStore.user?.username || '用户')

const avatarText = computed(() => {
  const name = displayName.value
  return (name[0] || '用').toUpperCase()
})

const onDocClick = () => {
  ElMessage.info('文档中心即将上线')
}

const goWithQuery = (mode) => {
  router.push({ path: '/security/projects', query: { action: mode } })
}

const handleCommand = (command) => {
  if (command === 'profile') {
    router.push('/user/profile')
  } else if (command === 'logout') {
    userStore.logout()
    ElMessage.success('已退出登录')
    router.push('/login')
  }
}

onMounted(async () => {
  try {
    const response = await securityAPI.getWorkbenchOverview()
    const totals = response.data?.totals || {}
    vulnBadge.value = (totals.critical || 0) + (totals.high || 0)
  } catch (error) {
    vulnBadge.value = 0
  }
})

watch(() => route.path, () => {
  mobileSidebarOpen.value = false
})
</script>

<style scoped lang="scss">
.wb-shell {
  min-height: 100vh;
  background: #fff;
  color: #0f172a;
}

.topbar {
  position: sticky;
  top: 0;
  z-index: 100;
  height: 60px;
  display: flex;
  align-items: center;
  gap: 24px;
  padding: 0 24px;
  background: #fff;
  border-bottom: 1px solid #e2e8f0;

  .brand {
    display: flex;
    align-items: center;
    gap: 10px;
    cursor: pointer;
    flex: 0 0 auto;

    .brand-logo {
      width: 32px;
      height: 32px;
      border-radius: 8px;
      background: #2563eb;
      color: #fff;
      font-size: 13px;
      font-weight: 700;
      display: flex;
      align-items: center;
      justify-content: center;
      letter-spacing: 0.02em;
    }

    .brand-name {
      font-size: 16px;
      font-weight: 700;
      letter-spacing: -0.01em;
    }

    .brand-sub {
      font-size: 12px;
      color: #94a3b8;
    }
  }

  .mobile-menu-btn {
    display: none;
    width: 34px;
    height: 34px;
    padding: 0;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    background: #fff;
    color: #475569;
  }

  .top-nav {
    display: flex;
    align-items: center;
    gap: 4px;
    margin: 0 auto;

    .top-nav__item {
      padding: 6px 14px;
      border-radius: 8px;
      font-size: 14px;
      color: #475569;
      cursor: pointer;
      text-decoration: none;
      transition: background 0.15s ease, color 0.15s ease;

      &:hover:not(.top-nav__item--disabled) {
        color: #2563eb;
        background: #eff6ff;
      }

      &--active {
        color: #2563eb;
        font-weight: 600;
        background: #eff6ff;
      }

      &--disabled {
        color: #cbd5e1;
        cursor: not-allowed;
      }
    }
  }

  .top-actions {
    display: flex;
    align-items: center;
    gap: 10px;
    flex: 0 0 auto;

    .user-trigger {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      cursor: pointer;
      outline: none;

      .user-avatar {
        background: #2563eb;
        color: #fff;
        font-size: 13px;
        font-weight: 600;
      }

      .user-name {
        max-width: 120px;
        overflow: hidden;
        color: #334155;
        font-size: 13px;
        font-weight: 500;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
    }
  }
}

.wb-body {
  display: flex;
  align-items: flex-start;
}

.sidebar {
  position: sticky;
  top: 60px;
  width: 240px;
  height: calc(100vh - 60px);
  flex: 0 0 auto;
  overflow-y: auto;
  padding: 16px 12px 32px;
  background: #fff;
  border-right: 1px solid #e2e8f0;
  z-index: 120;

  .side-group + .side-group {
    margin-top: 24px;
  }

  .side-title {
    margin: 0 0 8px;
    padding: 0 10px;
    font-size: 12px;
    color: #94a3b8;
    letter-spacing: 0.08em;
  }

  .side-item {
    display: flex;
    align-items: center;
    gap: 10px;
    height: 38px;
    margin-bottom: 2px;
    padding: 0 10px;
    border-radius: 8px;
    font-size: 14px;
    color: #475569;
    text-decoration: none;
    cursor: pointer;
    transition: background 0.15s ease, color 0.15s ease;

    .el-icon {
      font-size: 16px;
    }

    &:hover:not(.side-item--disabled) {
      background: #f1f5f9;
      color: #0f172a;
    }

    &--active {
      background: #eff6ff;
      color: #2563eb;
      font-weight: 600;
    }

    &--disabled {
      color: #cbd5e1;
      cursor: not-allowed;
    }

    .side-badge {
      margin-left: auto;
      min-width: 20px;
      height: 20px;
      padding: 0 6px;
      border-radius: 10px;
      background: #dc2626;
      color: #fff;
      font-size: 11px;
      font-weight: 600;
      display: inline-flex;
      align-items: center;
      justify-content: center;
    }
  }
}

.sidebar-backdrop {
  display: none;
}

.wb-main {
  flex: 1;
  min-width: 0;
  background: #fff;
}

@media (max-width: 1024px) {
  .topbar .top-nav {
    display: none;
  }
}

@media (max-width: 768px) {
  .topbar {
    .mobile-menu-btn {
      display: inline-flex;
      align-items: center;
      justify-content: center;
    }

    .brand-sub,
    .btn-doc,
    .btn-gh,
    .user-name {
      display: none;
    }
  }

  .sidebar {
    position: fixed;
    top: 60px;
    left: 0;
    bottom: 0;
    display: block;
    width: min(280px, 86vw);
    height: auto;
    transform: translateX(-100%);
    transition: transform 0.2s ease;
    box-shadow: 12px 0 28px rgba(15, 23, 42, 0.12);

    &--open {
      transform: translateX(0);
    }
  }

  .sidebar-backdrop {
    position: fixed;
    inset: 60px 0 0;
    z-index: 110;
    display: block;
    border: 0;
    background: rgba(15, 23, 42, 0.3);
  }
}
</style>
