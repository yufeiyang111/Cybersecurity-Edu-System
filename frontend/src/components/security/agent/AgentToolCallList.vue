<template>
  <section class="tools-card">
    <div class="card-head">
      <h2>工具调用</h2>
      <span class="note">{{ toolCalls.length }} 次</span>
    </div>
    <el-empty v-if="!loading && errorMessage" :description="errorMessage" :image-size="72" />
    <el-empty v-else-if="!loading && toolCalls.length === 0" description="尚无工具调用" :image-size="72" />
    <div v-else class="tool-list">
      <div v-for="call in toolCalls" :key="call.id" class="tool-row">
        <span class="tool-row__dot" :class="`tool-row__dot--${call.status}`" aria-hidden="true" />
        <div class="tool-row__body">
          <div class="tool-row__row">
            <span class="tool-row__name">{{ call.tool_name }}</span>
            <el-tag :type="metaOf(call.status).tagType" size="small">{{ metaOf(call.status).label }}</el-tag>
            <span v-if="call.latency_ms != null" class="tool-row__latency">{{ call.latency_ms }} ms</span>
          </div>
          <div v-if="call.summary" class="tool-row__summary">{{ call.summary }}</div>
          <div v-if="call.warning_codes?.length" class="tool-row__warnings">
            警告：{{ call.warning_codes.join(', ') }}
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { toolStatusMetaOf } from '@/features/security/agent/statusMeta'

defineProps({
  toolCalls: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  errorMessage: { type: String, default: '' }
})

const metaOf = (status) => toolStatusMetaOf(status)
</script>

<style scoped lang="scss">
.tools-card { background: #fff; border: 1px solid #e2e7ee; border-radius: 8px; padding: 14px 16px; }
.card-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.card-head h2 { margin: 0; font-size: 15px; font-weight: 600; }
.card-head .note { color: #6a7890; font-size: 12.5px; }
.tool-list { display: flex; flex-direction: column; gap: 8px; max-height: 360px; overflow-y: auto; }
.tool-row { display: flex; gap: 10px; border: 1px solid #eef2f7; border-radius: 6px; padding: 8px 10px; background: #fafbfd; }
.tool-row__dot { width: 8px; height: 8px; border-radius: 50%; margin-top: 6px; flex: none; }
.tool-row__dot--running { background: #1d4ed8; }
.tool-row__dot--succeeded { background: #1c8a4d; }
.tool-row__dot--failed { background: #d43b3b; }
.tool-row__body { min-width: 0; flex: 1; }
.tool-row__row { display: flex; align-items: center; gap: 8px; }
.tool-row__name { font-size: 13px; font-weight: 600; color: #1f2d3d; font-family: ui-monospace, SFMono-Regular, Consolas, monospace; }
.tool-row__latency { color: #8494a8; font-size: 12px; }
.tool-row__summary { color: #52627a; font-size: 12.5px; margin-top: 2px; line-height: 1.5; }
.tool-row__warnings { color: #b54708; font-size: 12px; margin-top: 2px; }
</style>
