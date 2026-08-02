<template>
  <div class="info-card">
    <div class="info-row">
      <el-icon class="info-icon"><Message /></el-icon>
      <div class="info-body">
        <span class="info-label">邮箱</span>
        <span class="info-value">{{ userStore.user?.email || '未设置' }}</span>
      </div>
    </div>

    <div class="info-row">
      <el-icon class="info-icon"><Postcard /></el-icon>
      <div class="info-body">
        <span class="info-label">昵称</span>
        <span class="info-value">{{ userStore.user?.nickname || '未设置' }}</span>
      </div>
    </div>

    <div class="info-row">
      <el-icon class="info-icon"><Calendar /></el-icon>
      <div class="info-body">
        <span class="info-label">注册日期</span>
        <span class="info-value mono">{{ createdAt.date }}</span>
      </div>
    </div>

    <div class="info-row">
      <el-icon class="info-icon"><Clock /></el-icon>
      <div class="info-body">
        <span class="info-label">注册时间</span>
        <span class="info-value mono">{{ createdAt.time }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()

const createdAt = computed(() => {
  const str = userStore.user?.created_at
  if (!str) return { date: '—', time: '—' }
  const d = new Date(str)
  const pad = (n) => String(n).padStart(2, '0')
  return {
    date: `${d.getFullYear()} / ${pad(d.getMonth() + 1)} / ${pad(d.getDate())}`,
    time: `${pad(d.getHours())} : ${pad(d.getMinutes())} : ${pad(d.getSeconds())}`
  }
})
</script>

<style lang="scss" scoped>
@use '@/styles/user-vars' as *;

.info-card {
  padding: 8px 16px;
  background: $bg-white;
  border: 1px solid $border-color;
  border-radius: 8px;
  box-shadow: $shadow-soft;
}

.info-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 0;
  border-bottom: 1px solid $border-lighter;

  &:last-child {
    border-bottom: none;
  }
}

.info-icon {
  font-size: 16px;
  color: $text-secondary;
  flex-shrink: 0;
}

.info-body {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.info-label {
  font-size: 12px;
  color: $text-placeholder;
}

.info-value {
  font-size: 13px;
  color: $text-regular;
  word-break: break-all;

  &.mono {
    font-family: $font-mono;
    font-size: 12px;
  }
}
</style>
