<template>
  <header v-if="run" class="agent-header">
    <div class="agent-header__main">
      <div class="agent-header__title">
        <h1>Agent 任务 #{{ run.id }}</h1>
        <el-tag :type="status.tagType" size="small">{{ status.label }}</el-tag>
        <el-tag v-if="planner" :type="planner.tagType" size="small">{{ planner.label }}</el-tag>
      </div>
      <div class="agent-header__meta">
        <span>模式：{{ mode.label }}</span>
        <span class="sep">·</span>
        <span>快照 #{{ run.snapshot_id }}</span>
        <span class="sep">·</span>
        <span>工具调用 {{ run.tool_call_count }}</span>
        <span class="sep">·</span>
        <span>状态版本 v{{ run.state_version }}</span>
        <span v-if="run.warning_codes?.length" class="warnings">
          警告 {{ run.warning_codes.join(', ') }}
        </span>
      </div>
      <div class="agent-header__goal" v-if="run.goal_text">{{ run.goal_text }}</div>
    </div>
    <div class="agent-header__actions">
      <el-button
        size="small"
        :loading="actionLoading.pause"
        :disabled="!store.canPause"
        @click="$emit('pause')"
      >暂停</el-button>
      <el-button
        size="small"
        type="primary"
        plain
        :loading="actionLoading.resume"
        :disabled="!store.canResume"
        @click="$emit('resume')"
      >恢复</el-button>
      <el-button
        size="small"
        type="danger"
        plain
        :loading="actionLoading.cancel"
        :disabled="!store.canCancel"
        @click="$emit('cancel')"
      >取消</el-button>
    </div>
  </header>
</template>

<script setup>
import { computed } from 'vue'
import { agentModeMeta, agentStatusMeta, plannerSourceLabel } from '@/features/security/agent/statusMeta'

const props = defineProps({
  run: { type: Object, default: null },
  store: { type: Object, required: true },
  actionLoading: { type: Object, default: () => ({}) }
})
defineEmits(['pause', 'resume', 'cancel'])

const status = computed(() => agentStatusMeta(props.run?.status))
const mode = computed(() => agentModeMeta(props.run?.mode))
const planner = computed(() => (props.run?.planner_source ? plannerSourceLabel(props.run.planner_source) : null))
</script>

<style scoped lang="scss">
.agent-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  background: #fff;
  border: 1px solid #e2e7ee;
  border-radius: 8px;
  padding: 14px 16px;
  flex-wrap: wrap;
}
.agent-header__main { min-width: 0; }
.agent-header__title { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.agent-header__title h1 { margin: 0; font-size: 17px; font-weight: 600; }
.agent-header__meta { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; margin-top: 6px; color: #6a7890; font-size: 12.5px; }
.agent-header__meta .sep { color: #c2ccd9; }
.agent-header__meta .warnings { color: #b54708; }
.agent-header__goal { margin-top: 8px; color: #1f2d3d; font-size: 13px; line-height: 1.5; }
.agent-header__actions { display: flex; gap: 8px; align-items: center; }
</style>
