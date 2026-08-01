<template>
  <p class="auth-switch-link">
    <span class="auth-switch-link__hint">{{ hint }}</span>
    <router-link class="auth-switch-link__action" :to="to">{{ action }}</router-link>
  </p>
</template>

<script setup>
defineProps({
  hint: { type: String, default: '' },
  action: { type: String, default: '' },
  to: { type: [String, Object], required: true }
})
</script>

<style lang="scss" scoped>
.auth-switch-link {
  margin: 16px 0 0;
  text-align: center;
  font-size: 14px;
  color: #6b6b6b;

  &__action {
    margin-left: 6px;
    font-weight: 600;
    color: #1a1a1a;
    text-decoration: underline;
    text-underline-offset: 3px;

    &:hover {
      color: #8d8d85;
    }
  }
}
</style>
