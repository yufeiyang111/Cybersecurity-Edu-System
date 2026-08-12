<template>
  <section class="provider-card">
    <div class="card-head">
      <h2>Provider 策略</h2>
      <el-tag v-if="saved" type="success" size="small">已保存</el-tag>
    </div>
    <div v-if="loading && !policy" class="provider-card__empty">策略加载中…</div>
    <template v-else-if="policy">
      <div class="provider-card__field">
        <span class="provider-card__label">允许的 Provider</span>
        <el-checkbox-group v-model="allowlist" size="small">
          <el-checkbox v-for="name in knownProviders" :key="name" :label="name" :value="name">
            {{ name }}
          </el-checkbox>
        </el-checkbox-group>
        <p v-if="!allowlist.length" class="provider-card__hint">留空表示不限制</p>
      </div>
      <div class="provider-card__field">
        <span class="provider-card__label">首选 Provider</span>
        <el-select v-model="preferred" size="small" clearable placeholder="跟随默认顺序">
          <el-option v-for="name in knownProviders" :key="name" :label="name" :value="name" />
        </el-select>
      </div>
      <el-button size="small" type="primary" plain :loading="saving" @click="save">
        保存策略
      </el-button>
    </template>
  </section>
</template>

<script setup>
import { ref, watch } from 'vue'
import { ElMessage } from '@/features/security/feedback'
import { agentAPI } from '@/api'

const props = defineProps({
  workspaceId: { type: Number, default: null }
})

const policy = ref(null)
const allowlist = ref([])
const preferred = ref(null)
const knownProviders = ref([])
const loading = ref(false)
const saving = ref(false)
const saved = ref(false)

async function load() {
  if (!props.workspaceId) return
  loading.value = true
  try {
    const response = await agentAPI.getProviderPolicy(props.workspaceId)
    const policyData = response?.policy || {}
    policy.value = policyData
    allowlist.value = [...(policyData.allowlist || [])]
    preferred.value = policyData.preferred_provider || null
    knownProviders.value = policyData.known_providers || []
  } catch (error) {
    ElMessage.error('加载 Provider 策略失败')
  } finally {
    loading.value = false
  }
}

async function save() {
  if (!props.workspaceId) return
  saving.value = true
  saved.value = false
  try {
    const response = await agentAPI.updateProviderPolicy(props.workspaceId, {
      allowlist: allowlist.value,
      preferred_provider: preferred.value
    })
    policy.value = response.policy
    saved.value = true
    setTimeout(() => {
      saved.value = false
    }, 2000)
  } catch (error) {
    ElMessage.error(error?.response?.data?.error || '保存失败')
  } finally {
    saving.value = false
  }
}

watch(
  () => props.workspaceId,
  (id) => {
    if (id) load()
  }
)
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

.card-head h2 {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
}

.provider-card__empty {
  color: #8494a8;
  font-size: 12.5px;
}

.provider-card__field {
  margin-bottom: 10px;
}

.provider-card__label {
  display: block;
  font-size: 12px;
  font-weight: 600;
  color: #6a7890;
  margin-bottom: 6px;
}

.provider-card__hint {
  margin: 4px 0 0;
  font-size: 11.5px;
  color: #a0aaba;
}
</style>
