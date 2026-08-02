<template>
  <div class="stats-card">
    <div class="stat">
      <div class="stat-num">{{ loading ? '—' : questions }}</div>
      <div class="stat-label">提问</div>
    </div>
    <div class="stat-divider" />
    <div class="stat">
      <div class="stat-num">{{ loading ? '—' : favorites }}</div>
      <div class="stat-label">收藏</div>
    </div>
    <div class="stat-divider" />
    <div class="stat">
      <div class="stat-num">{{ loading ? '—' : answers }}</div>
      <div class="stat-label">回答</div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  questions: { type: Number, default: 0 },
  favorites: { type: Number, default: 0 },
  answers: { type: Number, default: 0 },
  loading: { type: Boolean, default: false }
})
</script>

<style lang="scss" scoped>
@use '@/styles/user-vars' as *;

.stats-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 12px;
  background: $bg-white;
  border: 1px solid $border-color;
  border-radius: 8px;
  box-shadow: $shadow-soft;
}

.stat {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}

.stat-num {
  font-size: 22px;
  font-weight: 600;
  line-height: 1.2;
  color: $text-primary;
  font-variant-numeric: tabular-nums;
}

.stat-label {
  font-size: 12px;
  color: $text-secondary;
}

.stat-divider {
  width: 1px;
  height: 32px;
  background: $border-light;
}
</style>
