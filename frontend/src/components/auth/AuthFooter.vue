<template>
  <p class="auth-footer">
    {{ text }}
    <router-link class="auth-footer__link" to="/policies/terms">《用户协议》</router-link>
    及
    <router-link class="auth-footer__link" to="/policies/privacy">《隐私政策》</router-link>
  </p>
</template>

<script setup>
defineProps({
  text: { type: String, default: '登录即表示您同意' }
})
</script>

<style lang="scss" scoped>
.auth-footer {
  margin: 24px 0 0;
  text-align: center;
  font-size: 12px;
  color: #9a9a92;
  line-height: 1.6;

  &__link {
    color: #8d8d85;
    font-weight: 600;
    text-decoration: underline;
    text-underline-offset: 3px;

    &:hover {
      color: #1a1a1a;
    }
  }
}
</style>
