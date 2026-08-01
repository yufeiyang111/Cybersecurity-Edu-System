<template>
  <button
    type="submit"
    class="submit-button"
    :class="{ 'submit-button--loading': loading }"
    :disabled="disabled || loading"
  >
    <span class="submit-button__label">{{ text }}</span>
    <span class="submit-button__icon" aria-hidden="true">
      <svg
        v-if="!loading"
        viewBox="0 0 24 24"
        fill="none"
      >
        <path
          d="M4 12h15m0 0-6-6m6 6-6 6"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
        />
      </svg>
      <span v-else class="submit-button__spinner" />
    </span>
  </button>
</template>

<script setup>
defineProps({
  text: { type: String, default: '提交' },
  loading: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false }
})
</script>

<style lang="scss" scoped>
.submit-button {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  width: 100%;
  padding: 15px 20px;
  font-size: 15px;
  font-weight: 600;
  font-family: inherit;
  color: #ffffff;
  background: #8d8d85;
  border: none;
  border-radius: 14px;
  cursor: pointer;
  transition: background 0.2s ease, transform 0.1s ease, opacity 0.2s ease;

  &:hover:not(:disabled) {
    background: #76766f;
  }

  &:active:not(:disabled) {
    transform: translateY(1px);
  }

  &:disabled {
    cursor: not-allowed;
    opacity: 0.6;
  }

  &__icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;

    svg {
      width: 18px;
      height: 18px;
    }
  }

  &__spinner {
    width: 16px;
    height: 16px;
    border: 2px solid rgba(255, 255, 255, 0.4);
    border-top-color: #ffffff;
    border-radius: 50%;
    animation: submit-button-spin 0.7s linear infinite;
  }

  &--loading {
    pointer-events: none;
  }
}

@keyframes submit-button-spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
