<template>
  <div class="warning-block">
    <span class="wb-icon" aria-hidden="true">⚠</span>
    <div class="wb-body">
      <span class="wb-label">执行警告</span>
      <div class="wb-codes">
        <span
          v-for="code in codes"
          :key="code"
          class="wb-code"
        >
          {{ warningLabel(code) }}
        </span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  codes: { type: Array, default: () => [] }
})

const WARNING_LABELS = {
  AGENT_PLAN_MISSING: '缺少执行计划',
  AGENT_PLAN_REPAIR_EXHAUSTED: 'LLM 规划失败，已降级本地策略',
  AGENT_REPEATED_TOOL_CALL: '重复工具调用被拦截',
  AGENT_MODEL_ERRORS_EXCEEDED: '模型连续错误超限',
  AGENT_ITERATION_LIMIT_REACHED: '达到迭代上限',
  AGENT_BUDGET_EXHAUSTED: '预算耗尽',
  AGENT_BASELINE_MODEL_SUMMARY_FALLBACK: '模型未生成摘要，已用确定性摘要降级',
  AGENT_TOOL_INPUT_INVALID: '工具输入校验失败',
  AGENT_TOOL_FAILED: '工具执行失败',
  AGENT_LOOP_ITERATION_FAILED: '循环单轮异常',
  AGENT_MODEL_ACTION_INVALID: '模型动作无效'
}

const displayCodes = computed(() => props.codes || [])

function warningLabel(code) {
  return WARNING_LABELS[code] || code
}
</script>

<style scoped lang="scss">
.warning-block {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 14px;
  border: 1px solid var(--chat-warning-border);
  border-radius: var(--chat-radius);
  background: var(--chat-warning-bg);
}

.wb-icon {
  font-size: 14px;
  color: var(--chat-warning-ink);
  flex: none;
  line-height: 1.5;
}

.wb-body {
  flex: 1;
  min-width: 0;
}

.wb-label {
  display: block;
  font-size: 12px;
  font-weight: 600;
  color: var(--chat-warning-ink);
  margin-bottom: 4px;
}

.wb-codes {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.wb-code {
  font-size: 11.5px;
  color: var(--chat-warning-ink);
  background: rgba(255, 255, 255, 0.6);
  border-radius: 999px;
  padding: 2px 10px;
}
</style>
