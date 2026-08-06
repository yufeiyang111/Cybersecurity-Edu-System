<template>
  <section class="provider-card">
    <div class="card-head">
      <h2>LLM Provider</h2>
      <el-tag v-if="provider" type="success" size="small">已接入</el-tag>
      <el-tag v-else type="info" size="small">未调用</el-tag>
    </div>
    <p v-if="provider" class="provider-card__line">
      <span class="provider-card__name">{{ provider.provider }}</span>
      <span v-if="provider.model" class="provider-card__model">{{ provider.model }}</span>
    </p>
    <p v-else class="provider-card__empty">本次运行尚未产生 LLM 调用</p>
  </section>
</template>

<script setup>
defineProps({
  provider: { type: Object, default: null }
})
</script>

<style scoped lang="scss">
.provider-card {
  background: #fff;
  border: 1px solid #e2e7ee;
  border-radius: 8px;
  padding: 14px 16px;
}
.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}
.card-head h2 { margin: 0; font-size: 15px; font-weight: 600; }
.provider-card__line { margin: 0; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.provider-card__name { font-size: 13px; font-weight: 600; color: #1f2d3d; }
.provider-card__model {
  font-size: 12px;
  color: #2563eb;
  background: #eff6ff;
  border-radius: 999px;
  padding: 1px 8px;
}
.provider-card__empty { margin: 0; color: #8494a8; font-size: 12.5px; }
</style>
