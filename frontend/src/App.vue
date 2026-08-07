<template>
  <el-config-provider :locale="zhCn">
    <div class="app-container">
      <router-view :key="$route.fullPath" />
    </div>
  </el-config-provider>
</template>

<script setup>
import { onMounted } from 'vue'
import zhCn from 'element-plus/dist/locale/zh-cn.mjs'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()

onMounted(async () => {
  userStore.checkAuth()
  const { installCodeCopy } = await import('@/features/markdown/renderMarkdown')
  installCodeCopy()
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
