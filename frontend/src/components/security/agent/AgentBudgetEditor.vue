<template>
  <el-collapse class="budget-editor">
    <el-collapse-item name="budget" title="运行预算（可选）">
      <p class="budget-editor__note">留空表示不限制；达到 80% 触发软提醒，100% 后停止新的 LLM 调用。</p>
      <el-form label-position="top" class="budget-editor__form">
        <div class="budget-editor__grid">
          <el-form-item label="最大 LLM 调用次数">
            <el-input-number
              :model-value="budget.max_llm_calls"
              :min="1"
              :max="10000"
              controls-position="right"
              placeholder="不限"
              @update:model-value="setField('max_llm_calls', $event)"
            />
          </el-form-item>
          <el-form-item label="最大 Token 总量">
            <el-input-number
              :model-value="budget.max_total_tokens"
              :min="1000"
              :step="1000"
              :max="100000000"
              controls-position="right"
              placeholder="不限"
              @update:model-value="setField('max_total_tokens', $event)"
            />
          </el-form-item>
          <el-form-item label="估算成本上限（USD）">
            <el-input-number
              :model-value="budget.max_estimated_cost"
              :min="0.01"
              :step="0.1"
              :precision="2"
              controls-position="right"
              placeholder="不限"
              @update:model-value="setField('max_estimated_cost', $event)"
            />
          </el-form-item>
          <el-form-item label="最大运行时长（秒）">
            <el-input-number
              :model-value="budget.max_wall_clock_seconds"
              :min="60"
              :step="60"
              controls-position="right"
              placeholder="不限"
              @update:model-value="setField('max_wall_clock_seconds', $event)"
            />
          </el-form-item>
        </div>
      </el-form>
    </el-collapse-item>
  </el-collapse>
</template>

<script setup>
const props = defineProps({
  budget: { type: Object, default: () => ({}) }
})
const emit = defineEmits(['update:budget'])

function setField(field, value) {
  const next = { ...props.budget }
  if (value == null || value === '') {
    delete next[field]
  } else {
    next[field] = value
  }
  emit('update:budget', next)
}
</script>

<style scoped lang="scss">
.budget-editor { border: 0; margin-top: 2px; }
.budget-editor__note { margin: 0 0 10px; color: #6a7890; font-size: 12px; line-height: 1.5; }
.budget-editor__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 14px;
}
.budget-editor__form :deep(.el-form-item) { margin-bottom: 10px; }
:deep(.el-input-number) { width: 100%; }
@media (max-width: 720px) {
  .budget-editor__grid { grid-template-columns: 1fr; }
}
</style>
