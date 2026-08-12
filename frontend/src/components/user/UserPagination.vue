<template>
  <nav class="user-pagination">
    <button
      type="button"
      class="user-pagination__btn"
      :disabled="modelValue <= 1"
      @click="change(modelValue - 1)"
    >
      ‹
    </button>
    <span class="user-pagination__info">
      {{ modelValue }} / {{ pages }}
    </span>
    <button
      type="button"
      class="user-pagination__btn"
      :disabled="modelValue >= pages"
      @click="change(modelValue + 1)"
    >
      ›
    </button>
  </nav>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  modelValue: { type: Number, required: true },
  total: { type: Number, default: 0 },
  perPage: { type: Number, default: 10 }
})

const emit = defineEmits(['update:modelValue', 'change'])

const pages = computed(() => {
  return Math.max(1, Math.ceil(props.total / props.perPage))
})

const change = (next) => {
  if (next < 1 || next > pages.value) return
  emit('update:modelValue', next)
  emit('change', next)
}
</script>

<style lang="scss" scoped>
@use '@/styles/user-vars' as *;

.user-pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 14px;
  border-top: 1px solid $border-lighter;
}

.user-pagination__btn {
  width: 30px;
  height: 30px;
  border: 1px solid $border-color;
  border-radius: 6px;
  background: $bg-white;
  color: $text-regular;
  font-size: 14px;
  line-height: 1;
  cursor: pointer;
  transition: background 0.15s ease, border-color 0.15s ease;

  &:hover:not(:disabled) {
    background: $bg-hover;
    border-color: $brand-border;
    color: $brand-color;
  }

  &:disabled {
    opacity: 0.45;
    cursor: not-allowed;
  }
}

.user-pagination__info {
  color: $text-secondary;
  font-size: 13px;
  font-variant-numeric: tabular-nums;
}
</style>
