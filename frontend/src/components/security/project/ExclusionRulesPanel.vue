<template>
  <aside class="exclusion-panel" aria-label="扫描排除规则">
    <div class="exclusion-panel__head">
      <h2>排除规则</h2>
      <el-tag v-if="rules.length" size="small" effect="plain">{{ rules.length }} 条</el-tag>
    </div>
    <p class="exclusion-panel__desc">
      类似 .gitignore：匹配到的文件不进入快照、不参与扫描与分析，避免敏感文件进入处理范围。
    </p>

    <el-alert
      v-if="dirty"
      title="规则已修改，需重新扫描后生效"
      type="warning"
      :closable="false"
      show-icon
      class="exclusion-panel__notice"
    >
      <template #default>
        <el-button size="small" :loading="rescanLoading" @click="triggerRescan">立即重新扫描</el-button>
      </template>
    </el-alert>

    <div v-if="errorMessage" class="exclusion-panel__error">{{ errorMessage }}</div>

    <div class="exclusion-panel__input">
      <el-input
        v-model="draft"
        size="small"
        placeholder="如 *.xlsx、docs/private/、!重要.md"
        :disabled="!canEdit"
        @keyup.enter="submitDraft"
      />
      <el-button size="small" type="primary" :disabled="!canEdit" :loading="submitting" @click="submitDraft">添加</el-button>
    </div>

    <el-empty v-if="!loading && rules.length === 0" description="暂无排除规则" :image-size="48" />

    <ul v-else class="exclusion-panel__list" aria-label="排除规则列表">
      <li v-for="rule in rules" :key="rule.id" class="exclusion-rule">
        <code class="exclusion-rule__pattern">{{ rule.pattern }}</code>
        <el-button
          v-if="canEdit"
          text
          type="danger"
          size="small"
          aria-label="删除规则"
          @click="removeRule(rule)"
        >删除</el-button>
      </li>
    </ul>

    <div class="exclusion-panel__syntax">
      <h3>语法示例</h3>
      <ul>
        <li><code>*.xlsx</code> 任意层级匹配</li>
        <li><code>docs/private/</code> 目录整体排除</li>
        <li><code>/secret.txt</code> 仅仓库根</li>
        <li><code>!重要说明.md</code> 重新包含</li>
        <li><code># 注释</code> 忽略该行</li>
      </ul>
    </div>
  </aside>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from '@/features/security/feedback'
import { securityAPI } from '@/api'
import { securityApiErrorMessage } from '@/features/security/presentation'

const props = defineProps({
  projectId: { type: [Number, String], required: true },
  canEdit: { type: Boolean, default: false },
  rescanLoading: { type: Boolean, default: false }
})

const emit = defineEmits(['rescan'])

const rules = ref([])
const draft = ref('')
const loading = ref(false)
const submitting = ref(false)
const dirty = ref(false)
const errorMessage = ref('')

const load = async () => {
  loading.value = true
  errorMessage.value = ''
  try {
    const response = await securityAPI.getExclusions(props.projectId)
    rules.value = response.items || []
  } catch (error) {
    errorMessage.value = securityApiErrorMessage(error, '加载排除规则失败。')
  } finally {
    loading.value = false
  }
}

const submitDraft = async () => {
  const pattern = draft.value.trim()
  if (!pattern) return
  submitting.value = true
  errorMessage.value = ''
  try {
    await securityAPI.addExclusion(props.projectId, pattern)
    draft.value = ''
    dirty.value = true
    await load()
  } catch (error) {
    errorMessage.value = securityApiErrorMessage(error, '添加规则失败。')
  } finally {
    submitting.value = false
  }
}

const removeRule = async (rule) => {
  errorMessage.value = ''
  try {
    await securityAPI.deleteExclusion(props.projectId, rule.id)
    dirty.value = true
    await load()
  } catch (error) {
    errorMessage.value = securityApiErrorMessage(error, '删除规则失败。')
  }
}

const triggerRescan = () => {
  emit('rescan')
}

onMounted(load)
</script>

<style scoped lang="scss">
.exclusion-panel {
  display: flex;
  min-height: 100%;
  flex-direction: column;
  gap: 10px;
  padding: 17px 16px;
  border: 1px solid #dfe6ef;
  border-radius: 10px;
  background: #ffffff;
  box-shadow: 0 3px 12px rgba(21, 40, 75, 0.04);
  transition: border-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease;
}

.exclusion-panel:hover {
  border-color: #c4d3e4;
  box-shadow: 0 10px 22px rgba(21, 40, 75, 0.08);
  transform: translateY(-1px);
}
.exclusion-panel__head { display: flex; align-items: center; justify-content: space-between; }
.exclusion-panel__head h2 { margin: 0; font-size: 15px; font-weight: 600; }
.exclusion-panel__desc { margin: 0; color: #7e8da3; font-size: 12px; line-height: 1.6; }
.exclusion-panel__notice { margin: 0; }
.exclusion-panel__notice :deep(.el-alert__content) { display: flex; flex-direction: column; gap: 8px; align-items: flex-start; }
.exclusion-panel__error { color: #d43b3b; font-size: 12.5px; }
.exclusion-panel__input { display: flex; gap: 8px; }
.exclusion-panel__list { display: flex; flex-direction: column; gap: 6px; margin: 0; padding: 0; list-style: none; max-height: 320px; overflow-y: auto; }
.exclusion-rule {
  display: flex; align-items: center; justify-content: space-between; gap: 8px;
  padding: 7px 10px; border: 1px solid #e2e7ee; border-radius: 7px; background: #f8fafc;
  transition: border-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease;
}
.exclusion-rule:hover {
  border-color: #c4d3e4;
  box-shadow: 0 5px 12px rgba(21, 40, 75, 0.06);
  transform: translateX(2px);
}
.exclusion-rule__pattern { font-size: 12.5px; color: #1f2d3d; word-break: break-all; }
.exclusion-panel__syntax { border-top: 1px dashed #e2e7ee; padding-top: 10px; }
.exclusion-panel__syntax h3 { margin: 0 0 6px; font-size: 12.5px; color: #6a7890; font-weight: 600; }
.exclusion-panel__syntax ul { margin: 0; padding-left: 2px; list-style: none; }
.exclusion-panel__syntax li { color: #52627a; font-size: 12px; line-height: 1.9; }
.exclusion-panel__syntax code { background: #f0f4f8; border-radius: 4px; padding: 1px 5px; font-size: 11.5px; }
.exclusion-panel__list::-webkit-scrollbar { width: 6px; }
.exclusion-panel__list::-webkit-scrollbar-thumb { background: #ccd5e0; border-radius: 3px; }
</style>
