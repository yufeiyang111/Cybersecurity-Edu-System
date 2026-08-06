<template>
  <main class="llm-page">
    <LlmProviderToolbar :loading="loading" @create="openCreate" @test-all="testAll" />
    <div v-if="errorMessage" class="page-error"><BaseIcon name="alert-triangle" :size="16" />{{ errorMessage }}</div>
    <BasePanel class="filter-panel"><template #default><div class="filter-row"><input v-model.trim="searchName" class="filter-input" placeholder="按名称筛选..." /><input v-model.trim="searchUrl" class="filter-input" placeholder="按 API 地址筛选..." /><select v-model="statusFilter" class="filter-select"><option value="">状态</option><option value="enabled">已启用</option><option value="disabled">已禁用</option></select><span class="filter-spacer" /><BaseButton variant="ghost" @click="clearFilters"><BaseIcon name="refresh" :size="14" />重置</BaseButton><BaseButton><BaseIcon name="eye" :size="14" />查看</BaseButton></div></template></BasePanel>
    <BasePanel class="table-panel"><template #default><LlmProviderTable :providers="filteredProviders" :loading="loading" :testing="testing" @create="openCreate" @test="testProvider" @edit="openEdit" @delete="deleteProvider" /></template><template #footer><div class="table-footer"><span>总计：{{ filteredProviders.length }}</span><div><span class="page-size">每页行数 <select><option>20</option></select></span><button class="page-button" disabled>‹</button><button class="page-button active">1</button><button class="page-button">›</button></div></div></template></BasePanel>
    <LlmProviderFormDialog v-model="dialogVisible" :provider="selectedProvider" :submitting="submitting" @submit="saveProvider" />
  </main>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from '@/features/security/feedback'
import { BaseButton, BaseIcon, BasePanel } from '@/components/ui'
import LlmProviderFormDialog from '@/components/security/llm/LlmProviderFormDialog.vue'
import LlmProviderTable from '@/components/security/llm/LlmProviderTable.vue'
import LlmProviderToolbar from '@/components/security/llm/LlmProviderToolbar.vue'
import { useLlmProviders } from '@/composables/security/useLlmProviders'

const { providers, loading, errorMessage, load, create, update, remove, test, testing } = useLlmProviders()
const searchName = ref('')
const searchUrl = ref('')
const statusFilter = ref('')
const dialogVisible = ref(false)
const selectedProvider = ref(null)
const submitting = ref(false)
const filteredProviders = computed(() => providers.value.filter((provider) => {
  const nameMatch = !searchName.value || provider.name.toLowerCase().includes(searchName.value.toLowerCase())
  const urlMatch = !searchUrl.value || provider.base_url.toLowerCase().includes(searchUrl.value.toLowerCase())
  const statusMatch = !statusFilter.value || (statusFilter.value === 'enabled' ? provider.is_enabled : !provider.is_enabled)
  return nameMatch && urlMatch && statusMatch
}))
const openCreate = () => { selectedProvider.value = null; dialogVisible.value = true }
const openEdit = (provider) => { selectedProvider.value = provider; dialogVisible.value = true }
const clearFilters = () => { searchName.value = ''; searchUrl.value = ''; statusFilter.value = '' }
const saveProvider = async (payload) => { submitting.value = true; try { if (selectedProvider.value) await update(selectedProvider.value.id, payload); else await create(payload); dialogVisible.value = false; ElMessage.success('LLM 配置已保存') } catch (error) { ElMessage.error(error?.response?.data?.error || '保存 LLM 配置失败') } finally { submitting.value = false } }
const testProvider = async (provider) => { try { const response = await test(provider.id); if (response.check?.status === 'healthy') { ElMessage.success({ message: '连接测试成功', duration: 3000 }) } else { const detail = response.check?.detail; const hint = response.check?.hint; ElMessage.warning({ message: detail ? `${detail}：${hint || ''}` : '连接测试未通过', duration: 5000 }) } } catch (error) { ElMessage.error(error?.response?.data?.error || '连接测试失败') } }
const testAll = async () => { for (const provider of filteredProviders.value) await testProvider(provider) }
const deleteProvider = async (provider) => { try { await ElMessageBox.confirm(`确定删除「${provider.name}」吗？`, '删除 LLM 配置', { type: 'warning' }); await remove(provider.id); ElMessage.success('LLM 配置已删除') } catch (error) { if (error !== 'cancel') ElMessage.error(error?.response?.data?.error || '删除 LLM 配置失败') } }
onMounted(load)
</script>

<style scoped lang="scss">
.llm-page {
  min-height: 100vh;
  padding: 28px 32px 70px;
  background: #ffffff;
  color: #0f172a;
}
.filter-row { display:flex;align-items:center;gap:9px;flex-wrap:wrap }.filter-input,.filter-select{height:34px;width:180px;padding:0 10px;border:1px solid #e2e8f0;border-radius:6px;background:#fff;color:#0f172a;font-size:12px;outline:none}.filter-input:focus,.filter-select:focus{border-color:#2563eb;box-shadow:0 0 0 3px rgba(37,99,235,.12)}.filter-spacer{flex:1}.page-error{display:flex;align-items:center;gap:8px;padding:11px 14px;margin-bottom:14px;border:1px solid #fecaca;border-radius:7px;background:#fef2f2;color:#dc2626;font-size:13px}.table-panel :deep(.ui-panel__body){padding:0}.table-footer{display:flex;align-items:center;justify-content:space-between;color:#475569;font-size:12px}.table-footer>div{display:flex;align-items:center;gap:6px}.page-size select{height:30px;margin-left:5px;border:1px solid #e2e8f0;border-radius:6px}.page-button{width:30px;height:30px;border:1px solid #e2e8f0;border-radius:6px;background:#fff;color:#475569}.page-button.active{border-color:#2563eb;background:#2563eb;color:#fff}.page-button:disabled{color:#cbd5e1}@media(max-width:900px){.llm-page{padding:22px 20px 60px}}@media(max-width:640px){.llm-page{padding:18px 12px 50px}.filter-input,.filter-select{width:100%}.filter-spacer{display:none}.filter-row :deep(.ui-btn){width:auto}}
</style>
