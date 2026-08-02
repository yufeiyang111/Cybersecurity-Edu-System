<template>
  <div class="avatar-card">
    <el-upload
      class="avatar-upload"
      :show-file-list="false"
      :before-upload="beforeUpload"
      :http-request="uploadHandler"
      accept="image/*"
    >
      <div class="avatar-box" v-loading="uploading">
        <el-avatar class="avatar-img" :size="avatarSize" :src="userStore.user?.avatar_url || undefined">
          {{ initial }}
        </el-avatar>
        <div class="avatar-mask">
          <el-icon><Camera /></el-icon>
          <span>更换头像</span>
        </div>
      </div>
    </el-upload>

    <div class="avatar-name">{{ displayName }}</div>
    <div class="avatar-role">
      <el-icon><Shield /></el-icon>
      <span>{{ getRoleText(userStore.user?.role) }}</span>
    </div>
    <div class="avatar-tip">支持 JPG · PNG · 200×200</div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useUserStore } from '@/stores/user'
import { getRoleText } from '@/features/user/roles'
import { useAvatarUpload } from '@/composables/user/useAvatarUpload'

const userStore = useUserStore()
const { uploading, beforeUpload, uploadHandler } = useAvatarUpload()

const displayName = computed(() => userStore.user?.nickname || userStore.user?.username || '未命名用户')
const initial = computed(() => userStore.user?.nickname?.[0] || userStore.user?.username?.[0] || '用户')
</script>

<style lang="scss" scoped>
@use '@/styles/user-vars' as *;

.avatar-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 24px 20px;
  background: $bg-white;
  border: 1px solid $border-color;
  border-radius: 8px;
  box-shadow: $shadow-soft;
}

.avatar-upload {
  cursor: pointer;
}

.avatar-box {
  position: relative;
  width: $avatar-size;
  height: $avatar-size;
  border-radius: 50%;
  overflow: hidden;
  transition: transform 0.2s ease;

  &:hover .avatar-mask {
    opacity: 1;
  }

  &:hover {
    transform: scale(1.02);
  }
}

.avatar-img {
  display: block;
  width: 100%;
  height: 100%;
  font-size: 40px;
  background: $brand-light;
  color: $brand-color;
}

.avatar-mask {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  background: rgba(0, 0, 0, 0.45);
  color: #fff;
  font-size: 12px;
  opacity: 0;
  transition: opacity 0.2s ease;
}

.avatar-name {
  margin-top: 16px;
  font-size: 20px;
  font-weight: 600;
  color: $text-primary;
}

.avatar-role {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 4px;
  font-size: 13px;
  color: $brand-color;

  .el-icon {
    font-size: 14px;
  }
}

.avatar-tip {
  margin-top: 8px;
  font-size: 12px;
  color: $text-placeholder;
}

@include respond-to('sm') {
  .avatar-box {
    width: $avatar-size-sm;
    height: $avatar-size-sm;
  }
}
</style>
