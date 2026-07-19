<template>
  <el-card class="stat-card" :class="[`stat-card--${type}`]">
    <div class="stat-content">
      <div class="stat-icon">
        <slot name="icon">
          <el-icon :size="24"><DataAnalysis /></el-icon>
        </slot>
      </div>
      <div class="stat-info">
        <span class="stat-value">{{ value }}</span>
        <span class="stat-label">{{ label }}</span>
      </div>
    </div>
    <div v-if="$slots.footer" class="stat-footer">
      <slot name="footer"></slot>
    </div>
  </el-card>
</template>

<script setup>
defineProps({
  value: {
    type: [String, Number],
    required: true
  },
  label: {
    type: String,
    required: true
  },
  type: {
    type: String,
    default: 'primary',
    validator: (v) => ['primary', 'success', 'warning', 'danger', 'info'].includes(v)
  }
})
</script>

<style lang="scss" scoped>
.stat-card {
  &--primary .stat-icon { background: linear-gradient(135deg, #667eea, #764ba2); }
  &--success .stat-icon { background: linear-gradient(135deg, #43e97b, #38f9d7); }
  &--warning .stat-icon { background: linear-gradient(135deg, #f093fb, #f5576c); }
  &--danger .stat-icon { background: linear-gradient(135deg, #ff9a9e, #fecfef); }
  &--info .stat-icon { background: linear-gradient(135deg, #4facfe, #00f2fe); }

  .stat-content {
    display: flex;
    align-items: center;
    gap: 16px;
  }

  .stat-icon {
    width: 56px;
    height: 56px;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #fff;
  }

  .stat-info {
    display: flex;
    flex-direction: column;
  }

  .stat-value {
    font-size: 24px;
    font-weight: 600;
    color: #303133;
  }

  .stat-label {
    font-size: 14px;
    color: #909399;
  }

  .stat-footer {
    margin-top: 12px;
    padding-top: 12px;
    border-top: 1px solid #f0f0f0;
  }
}
</style>
