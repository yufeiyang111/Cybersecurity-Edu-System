<template>
  <div class="brand-panel">
    <div class="brand-panel__top">
      <div class="brand-panel__logo">
        <span class="brand-panel__logo-mark" aria-hidden="true">
          <svg viewBox="0 0 36 36" fill="none">
            <rect width="36" height="36" rx="10" fill="#1a1a1a" />
            <path
              d="M11 10v16M25 10v16M14 18h14"
              stroke="#f6f5f1"
              stroke-width="3.4"
              stroke-linecap="round"
            />
          </svg>
        </span>
        <span class="brand-panel__logo-label">{{ logoLabel }}</span>
      </div>
      <p class="brand-panel__tagline">{{ tagline }}</p>
    </div>

    <div class="brand-panel__headline">
      <h1 class="brand-panel__title">{{ brandTitle }}</h1>
      <p class="brand-panel__subtitle">{{ brandSubtitle }}</p>
    </div>

    <div class="brand-panel__footer">
      <span class="brand-panel__line" aria-hidden="true" />
      <span v-if="footerNote" class="brand-panel__note">{{ footerNote }}</span>
    </div>
  </div>
</template>

<script setup>
defineProps({
  logoLabel: { type: String, default: 'HaoAI' },
  brandTitle: { type: String, default: 'HaoAI' },
  brandSubtitle: { type: String, default: '模型清晰，价格透明，从容开始。' },
  tagline: { type: String, default: '企业级安全运营与 DevSecOps 工作台' },
  footerNote: { type: String, default: '' }
})
</script>

<style lang="scss" scoped>
.brand-panel {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 48px;
  min-height: 100%;
  width: 100%;

  &__top {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  &__logo {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  &__logo-mark {
    display: inline-flex;

    svg {
      width: 36px;
      height: 36px;
    }
  }

  &__logo-label {
    font-size: 20px;
    font-weight: 800;
    letter-spacing: -0.02em;
    color: #1a1a1a;
  }

  &__tagline {
    font-size: 14px;
    color: #6b6b6b;
  }

  &__headline {
    display: flex;
    flex-direction: column;
    gap: 20px;
  }

  &__title {
    font-size: clamp(56px, 8vw, 108px);
    font-weight: 800;
    line-height: 0.98;
    letter-spacing: -0.04em;
    color: #1a1a1a;
  }

  &__subtitle {
    font-size: clamp(16px, 1.6vw, 20px);
    font-weight: 500;
    color: #4a4a45;
    max-width: 30ch;
  }

  &__footer {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  &__line {
    display: block;
    width: 64px;
    height: 4px;
    border-radius: 2px;
    background: #8d8d85;
  }

  &__note {
    font-size: 13px;
    color: #9a9a92;
  }

  @media (max-width: 900px) {
    gap: 32px;

    &__title {
      font-size: clamp(44px, 12vw, 64px);
    }

    &__subtitle {
      max-width: none;
    }
  }
}
</style>
