<template>
  <section v-if="patchDiff" class="patch-block">
    <div class="patch-block__header">
      <div>
        <strong>受限 Unified Diff</strong>
        <span>仅供复制到独立分支后人工验证，系统不会自动应用。</span>
      </div>
      <el-button text type="primary" size="small" @click="emit('copy', patchDiff)">复制 Diff</el-button>
    </div>
    <pre>{{ patchDiff }}</pre>
  </section>
  <p v-else class="no-patch">该建议未提供可审阅补丁，需结合业务语义人工修复。</p>
</template>

<script setup>
defineProps({
  patchDiff: { type: String, default: '' }
})

const emit = defineEmits(['copy'])
</script>

<style scoped lang="scss">
.patch-block { margin-top: 14px; padding: 14px; border-radius: 10px; background: #102a43; color: #eaf2f8; }
.patch-block__header { display: flex; gap: 12px; align-items: flex-start; justify-content: space-between; margin-bottom: 10px; }
.patch-block__header span { display: block; margin-top: 4px; color: #bcd2e4; font-size: 12px; line-height: 1.5; }
.patch-block pre { margin: 0; max-height: 360px; overflow: auto; white-space: pre-wrap; overflow-wrap: anywhere; font-size: 12px; line-height: 1.55; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
.no-patch { margin: 14px 0 0; color: #627d98; font-size: 13px; }
@media (max-width: 760px) { .patch-block__header { flex-direction: column; } }
</style>
