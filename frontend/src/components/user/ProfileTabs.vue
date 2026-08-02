<template>
  <nav class="profile-tabs">
    <router-link to="/user/profile" class="tab" exact-active-class="is-active">概览</router-link>
    <router-link to="/user/history" class="tab" active-class="is-active">
      问答历史
      <el-badge v-if="questions > 0" :value="questions" class="tab-badge" />
    </router-link>
    <router-link to="/user/favorites" class="tab" active-class="is-active">
      我的收藏
      <el-badge v-if="favorites > 0" :value="favorites" class="tab-badge" />
    </router-link>
    <a class="tab tab--anchor" :class="{ 'is-active': securityActive }" @click="handleSecurity">
      安全设置
    </a>
  </nav>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const props = defineProps({
  questions: { type: Number, default: 0 },
  favorites: { type: Number, default: 0 }
})

const route = useRoute()
const router = useRouter()

const securityActive = computed(() => route.path === '/user/profile' && route.hash === '#security')

const scrollToSecurity = () => {
  document.getElementById('security')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

const handleSecurity = () => {
  if (route.path === '/user/profile') {
    scrollToSecurity()
  } else {
    router.push({ path: '/user/profile', hash: '#security' })
  }
}
</script>

<style lang="scss" scoped>
@use '@/styles/user-vars' as *;

.profile-tabs {
  display: flex;
  gap: 4px;
  border-bottom: 1px solid $border-color;
  margin-bottom: 20px;
  overflow-x: auto;
}

.tab {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 10px 16px;
  font-size: 14px;
  font-weight: 500;
  color: $text-regular;
  white-space: nowrap;
  cursor: pointer;
  transition: color 0.2s ease;
  text-decoration: none;

  &::after {
    content: '';
    position: absolute;
    left: 0;
    right: 0;
    bottom: -1px;
    height: 2px;
    background: transparent;
    transition: background 0.2s ease;
  }

  &:hover {
    color: $text-primary;
  }

  &.is-active {
    color: $brand-color;

    &::after {
      background: $brand-color;
    }

    :deep(.el-badge__content) {
      background: $brand-color;
      border-color: $brand-color;
    }
  }
}

.tab-badge {
  margin-left: 2px;
}
</style>
