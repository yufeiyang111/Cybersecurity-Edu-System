<template>
  <div class="admin-layout">
    <header class="admin-header">
      <div class="header-content">
        <div class="logo" @click="$router.push('/')">
          <el-icon :size="28" color="#10b981"><Connection /></el-icon>
          <span>CyberGuard 管理后台</span>
        </div>
        <nav class="admin-nav">
          <router-link to="/admin/dashboard">系统概览</router-link>
          <router-link to="/admin/users">用户管理</router-link>
          <router-link to="/admin/knowledge">知识管理</router-link>
          <router-link to="/admin/policies">政策文档</router-link>
          <router-link to="/">返回前台</router-link>
        </nav>
        <div class="user-info">
          <el-dropdown @command="handleCommand">
            <span class="dropdown-trigger">
              <el-avatar :size="32" :src="userStore.user?.avatar_url || undefined">
                {{ userStore.user?.nickname?.[0] || userStore.user?.username?.[0] || '管理员' }}
              </el-avatar>
              <span>{{ userStore.user?.nickname || userStore.user?.username }}</span>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="logout">
                  <el-icon><SwitchButton /></el-icon>退出登录
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </div>
    </header>

    <main class="admin-main">
      <div class="main-container">
        <router-view />
      </div>
    </main>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { ElMessage } from 'element-plus'
import { Connection, SwitchButton } from '@element-plus/icons-vue'

const router = useRouter()
const userStore = useUserStore()

const handleCommand = (command) => {
  if (command === 'logout') {
    userStore.logout()
    ElMessage.success('已退出登录')
    router.push('/login')
  }
}
</script>

<style lang="scss" scoped>
.admin-layout {
  min-height: 100vh;
  background: #f5f7fa;
}

.admin-header {
  background: #fff;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);

  .header-content {
    max-width: 1400px;
    margin: 0 auto;
    padding: 0 20px;
    height: 60px;
    display: flex;
    align-items: center;
    gap: 40px;
  }

  .logo {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 18px;
    font-weight: 600;
    color: #303133;
    cursor: pointer;
  }

  .admin-nav {
    display: flex;
    gap: 32px;
    flex: 1;

    a {
      color: #606266;
      font-size: 15px;

      &:hover, &.router-link-active {
        color: #10b981;
      }
    }
  }

  .user-info {
    .dropdown-trigger {
      display: flex;
      align-items: center;
      gap: 8px;
      cursor: pointer;
      color: #606266;
    }
  }
}

.admin-main {
  padding: 24px 0;

  .main-container {
    max-width: 1400px;
    margin: 0 auto;
    padding: 0 20px;
  }
}
</style>
