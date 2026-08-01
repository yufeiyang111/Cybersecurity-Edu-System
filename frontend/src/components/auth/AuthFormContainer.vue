<template>
  <section class="auth-form-container">
    <div class="auth-form-container__header">
      <h2 class="auth-form-container__title">{{ title }}</h2>
      <p v-if="subtitle" class="auth-form-container__subtitle">{{ subtitle }}</p>
    </div>
    <slot />
  </section>
</template>

<script setup>
defineProps({
  title: { type: String, default: '' },
  subtitle: { type: String, default: '' }
})
</script>

<style lang="scss" scoped>
.auth-form-container {
  width: 100%;
  max-width: 420px;

  &__header {
    margin-bottom: 36px;
  }

  &__title {
    font-size: 32px;
    font-weight: 800;
    letter-spacing: -0.02em;
    color: #1a1a1a;
    line-height: 1.15;
  }

  &__subtitle {
    margin-top: 10px;
    font-size: 15px;
    color: #6b6b6b;
    line-height: 1.6;
  }

  @media (max-width: 900px) {
    max-width: 100%;
  }
}
</style>
