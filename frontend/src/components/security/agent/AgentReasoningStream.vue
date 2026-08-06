<template>
  <section class="reasoning-card" :class="{ 'reasoning-card--live': live }">
    <div class="card-head">
      <h2>模型思维链</h2>
      <el-tag v-if="live" type="primary" size="small">reasoning_live</el-tag>
      <el-tag v-else size="small" type="info">未运行</el-tag>
    </div>
    <p class="reasoning-card__note">
      实时展示模型正在做什么（reasoning delta）。思维链不持久化：刷新页面后仅保留用量统计与分析结论。
    </p>
    <el-collapse v-model="active" class="reasoning-card__collapse">
      <el-collapse-item name="stream" title="实时思维链内容">
        <pre v-if="text" class="reasoning-card__text">{{ text }}</pre>
        <span v-else class="reasoning-card__empty">等待模型输出…</span>
      </el-collapse-item>
    </el-collapse>
  </section>
</template>

<script setup>
import { ref } from 'vue'

defineProps({
  text: { type: String, default: '' },
  live: { type: Boolean, default: false }
})

const active = ref([])
</script>

<style scoped lang="scss">
.reasoning-card { background: #fff; border: 1px solid #e2e7ee; border-radius: 8px; padding: 14px 16px; }
.reasoning-card--live { border-color: #0b7fd1; }
.card-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
.card-head h2 { margin: 0; font-size: 15px; font-weight: 600; }
.reasoning-card__note { margin: 0 0 8px; color: #6a7890; font-size: 12.5px; line-height: 1.5; }
.reasoning-card__collapse { border: 0; }
.reasoning-card__text {
  margin: 0; max-height: 260px; overflow-y: auto; white-space: pre-wrap; word-break: break-word;
  font-size: 12.5px; line-height: 1.6; color: #1f2d3d; background: #fafbfd;
  border: 1px solid #eef2f7; border-radius: 6px; padding: 10px;
}
.reasoning-card__empty { color: #8494a8; font-size: 12.5px; }
</style>
