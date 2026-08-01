<template>
  <el-dialog
    :model-value="modelValue"
    title="从 GitHub 导入并扫描"
    width="min(600px, calc(100vw - 32px))"
    destroy-on-close
    :close-on-click-modal="!loading"
    :close-on-press-escape="!loading"
    @update:model-value="emit('update:modelValue', $event)"
    @closed="resetForm"
  >
    <ImportSafetyNotice />

    <el-form label-position="top" class="github-import-form" @submit.prevent="submit">
      <el-form-item label="目标安全项目" required>
        <el-select v-model="form.projectId" placeholder="请选择已授权的项目" class="full-width" :disabled="loading">
          <el-option v-for="project in projects" :key="project.id" :label="project.name" :value="project.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="公开 GitHub 仓库地址" required :error="repositoryUrlError">
        <el-input
          v-model.trim="form.repositoryUrl"
          placeholder="https://github.com/owner/repository"
          autocomplete="url"
          :disabled="loading"
          @input="repositoryUrlError = ''"
          @keyup.enter="submit"
        />
        <p class="field-help">只填写仓库主页地址；分支、Token 和私有仓库地址均不在本入口支持范围内。</p>
      </el-form-item>
      <el-alert v-if="error" type="error" :title="error" show-icon :closable="false" />
    </el-form>

    <template #footer>
      <el-button :disabled="loading" @click="emit('update:modelValue', false)">取消</el-button>
      <el-button type="primary" :loading="loading" :disabled="!canSubmit" @click="submit">创建受控扫描</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import ImportSafetyNotice from './ImportSafetyNotice.vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  projects: { type: Array, default: () => [] },
  initialProjectId: { type: [Number, String], default: null },
  loading: { type: Boolean, default: false },
  error: { type: String, default: '' }
})

const emit = defineEmits(['update:modelValue', 'submit'])
const form = reactive({ projectId: null, repositoryUrl: '' })
const repositoryUrlError = ref('')
const canSubmit = computed(() => Boolean(form.projectId && form.repositoryUrl.trim()))

const initializeForm = () => {
  form.projectId = props.initialProjectId ?? props.projects[0]?.id ?? null
  form.repositoryUrl = ''
  repositoryUrlError.value = ''
}

const resetForm = () => {
  form.projectId = null
  form.repositoryUrl = ''
  repositoryUrlError.value = ''
}

const submit = () => {
  if (!form.projectId) return
  if (!form.repositoryUrl.trim()) {
    repositoryUrlError.value = '请输入公开 GitHub 仓库地址。'
    return
  }
  emit('submit', { projectId: form.projectId, repositoryUrl: form.repositoryUrl })
}

watch(() => props.modelValue, (visible) => {
  if (visible) initializeForm()
})
</script>

<style scoped lang="scss">
.github-import-form { margin-top: 20px; }
.full-width { width: 100%; }
.field-help { margin: 7px 0 0; color: #627d98; font-size: 12px; line-height: 1.6; }
</style>
