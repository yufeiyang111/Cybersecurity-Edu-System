<template>
  <div class="auth-layout">
    <aside class="auth-layout__brand">
      <slot name="brand" />
    </aside>
    <main class="auth-layout__form">
      <slot name="form" />
    </main>
  </div>
</template>

<script setup>
// 布局容器：桌面端左右分栏，移动端折叠为上下。
// 品牌区与表单区通过具名插槽注入，便于登录/注册等页面完全复用。
</script>

<style lang="scss" scoped>
.auth-layout {
  display: grid;
  grid-template-columns: 1.08fr 1fr;
  min-height: 100vh;
  font-family: 'Plus Jakarta Sans', 'Inter', -apple-system, BlinkMacSystemFont,
    'Segoe UI', 'Noto Sans', Helvetica, Arial, sans-serif;
  -webkit-font-smoothing: antialiased;

  &__brand {
    display: flex;
    flex-direction: column;
    background: #f6f5f1;
    padding: clamp(32px, 5vw, 80px);
  }

  &__form {
    display: flex;
    align-items: center;
    justify-content: center;
    background: #ffffff;
    padding: clamp(28px, 5vw, 80px);
  }

  @media (max-width: 900px) {
    grid-template-columns: 1fr;

    &__brand {
      padding: 32px 24px 48px;
    }

    &__form {
      padding: 40px 24px 64px;
      align-items: flex-start;
    }
  }
}
</style>
