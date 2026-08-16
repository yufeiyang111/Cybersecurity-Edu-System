<template>
  <div
    v-if="loading"
    class="attack-path-state__skeleton"
    aria-busy="true"
    aria-live="polite"
  >
    <span />
    <span />
    <span />
  </div>

  <div
    v-else-if="errorMessage"
    class="attack-path-state attack-path-state--error"
    role="alert"
  >
    <BaseIcon
      name="alert-triangle"
      :size="16"
    />
    <p>{{ errorMessage }}</p>
    <BaseButton
      variant="ghost"
      type="button"
      @click="$emit('retry')"
    >
      重试
    </BaseButton>
  </div>

  <div
    v-else
    class="attack-path-state"
  >
    <BaseIcon
      name="shield"
      :size="22"
    />
    <p>{{ emptyMessage }}</p>
  </div>
</template>

<script setup>
import {
  BaseButton,
  BaseIcon,
} from '@/components/ui'

defineProps({
  loading: {
    type: Boolean,
    default: false,
  },
  errorMessage: {
    type: String,
    default: '',
  },
  emptyMessage: {
    type: String,
    default: '',
  },
})

defineEmits(['retry'])
</script>

<style scoped lang="scss">
.attack-path-state {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 12px;
  border: 1px dashed #cbd5e1;
  border-radius: 6px;
  color: #64748b;
}

.attack-path-state p {
  margin: 0;
  font-size: 12px;
  line-height: 1.6;
}

.attack-path-state--error {
  align-items: center;
  border-color: #fecaca;
  background: #fef2f2;
  color: #b91c1c;
}

.attack-path-state--error p {
  flex: 1;
}

.attack-path-state__skeleton {
  display: grid;
  gap: 8px;
}

.attack-path-state__skeleton span {
  display: block;
  height: 74px;
  border-radius: 8px;
  background: linear-gradient(90deg, #f1f5f9 25%, #e2e8f0 37%, #f1f5f9 63%);
  background-size: 400% 100%;
  animation: attack-path-loading 1.3s ease infinite;
}

@keyframes attack-path-loading {
  0% {
    background-position: 100% 50%;
  }

  100% {
    background-position: 0 50%;
  }
}
</style>
