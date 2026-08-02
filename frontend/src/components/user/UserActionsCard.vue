<template>
  <div class="actions-card">
    <el-button
      class="action-btn action-btn--primary"
      :loading="saving"
      @click="$emit('save')"
    >
      保存修改
    </el-button>
    <el-button
      class="action-btn action-btn--danger"
      text
      @click="$emit('password')"
    >
      修改密码
    </el-button>
  </div>
</template>

<script setup>
defineProps({
  saving: { type: Boolean, default: false }
})

defineEmits(['save', 'password'])
</script>

<style lang="scss" scoped>
@use '@/styles/user-vars' as *;

.actions-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 16px;
  background: $bg-white;
  border: 1px solid $border-color;
  border-radius: 8px;
  box-shadow: $shadow-soft;
}

.action-btn {
  width: 100%;
  border-radius: 8px;
}

.action-btn--primary {
  color: #ffffff;
  background: $brand-color;
  border-color: $brand-color;

  &:hover,
  &:focus {
    color: #ffffff;
    background: $brand-hover;
    border-color: $brand-hover;
  }
}

.action-btn--danger {
  --el-button-text-color: #{$danger-color};
  --el-button-hover-text-color: #{$danger-color};
  --el-button-hover-bg-color: #{$danger-light};
  --el-button-active-bg-color: #{$danger-light};
}
</style>
