<template>
  <section class="goal-form">
    <div class="goal-form__head">
      <h2>创建 Agent 任务</h2>
      <span class="goal-form__note">填写审计目标并选择运行模式，任务会保留执行过程与结果。</span>
    </div>
    <el-form label-position="top" @submit.prevent="submit">
      <el-form-item label="审计目标">
        <el-input
          v-model="goal"
          type="textarea"
          :rows="4"
          maxlength="4000"
          show-word-limit
          placeholder="例如：先清点项目文件并告诉我项目结构"
        />
      </el-form-item>
      <el-form-item label="运行模式">
        <el-select v-model="mode" style="width: 260px">
          <el-option
            v-for="(meta, key) in agentRunModeMeta"
            :key="key"
            :value="key"
            :label="meta.label"
          >
            <span>{{ meta.label }}</span>
            <span class="goal-form__mode-desc">{{ meta.description }}</span>
          </el-option>
        </el-select>
      </el-form-item>
      <AgentBudgetEditor v-model:budget="budget" />
      <el-button type="primary" :loading="submitting" :disabled="!goal.trim()" native-type="submit">
        创建任务
      </el-button>
    </el-form>
  </section>
</template>

<script setup>
import { ref } from 'vue'
import AgentBudgetEditor from '@/components/security/agent/AgentBudgetEditor.vue'
import { agentRunModeMeta } from '@/features/security/agent/statusMeta'

const props = defineProps({
  submitting: { type: Boolean, default: false }
})
const emit = defineEmits(['create'])

const goal = ref('')
const mode = ref('baseline')
const budget = ref({})

function submit() {
  if (!goal.value.trim() || props.submitting) return
  emit('create', { goal: goal.value.trim(), mode: mode.value, budget: budget.value })
}
</script>

<style scoped lang="scss">
.goal-form {
  background: #fff;
  border: 1px solid #e2e7ee;
  border-radius: 8px;
  padding: 14px 16px;
}
.goal-form__head { margin-bottom: 10px; }
.goal-form__head h2 { margin: 0 0 4px; font-size: 15px; font-weight: 600; }
.goal-form__note { color: #6a7890; font-size: 12.5px; }
.goal-form__mode-desc { float: right; color: #8494a8; font-size: 12px; }
:deep(.el-form-item) { margin-bottom: 14px; }
</style>
