<template>
  <p class="auth-footer">{{ text }}</p>
</template>

<script setup>
defineProps({
  text: { type: String, default: '登录即表示您同意用户协议及隐私政策' }
})
</script>

<style lang="scss" scoped>
.auth-footer {
  margin: 24px 0 0;
  text-align: center;
  font-size: 12px;
  color: #9a9a92;
  line-height: 1.6;
}
</style>
