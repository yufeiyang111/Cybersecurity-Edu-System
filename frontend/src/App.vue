<template>
  <div class="app-container">
    <router-view :key="$route.fullPath" />
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()

onMounted(() => {
  // 检查登录状态
  userStore.checkAuth()
})
</script>

<style lang="scss">
html, body {
  margin: 0;
  padding: 0;
  height: 100%;
}

.app-container {
  min-height: 100vh;
  background: #f6f8fa;
}
</style>
