<template>
  <el-dialog
    :model-value="modelValue"
    title="设置"
    width="min(760px, calc(100vw - 32px))"
    class="chat-settings-dialog"
    destroy-on-close
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <div class="settings-layout">
      <nav class="settings-nav" aria-label="设置分类">
        <button v-for="tab in tabs" :key="tab.key" :class="{ active: activeTab === tab.key }" @click="activeTab = tab.key">
          {{ tab.label }}
        </button>
      </nav>

      <section class="settings-content">
        <ChatAppearanceSettings v-if="activeTab === 'appearance'" v-model="preferences" />
        <ChatPersonalizationSettings v-else-if="activeTab === 'personalization'" v-model="preferences" />
        <ChatGeneralSettings v-else v-model="preferences" />
      </section>
    </div>
    <template #footer>
      <el-button type="danger" plain @click="handleReset">重置</el-button>
      <span class="footer-spacer"></span>
      <el-button @click="$emit('update:modelValue', false)">取消</el-button>
      <el-button type="primary" :loading="saving" @click="handleSave">保存设置</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useChatPreferences } from '@/composables/chat/useChatPreferences'
import ChatAppearanceSettings from './settings/ChatAppearanceSettings.vue'
import ChatGeneralSettings from './settings/ChatGeneralSettings.vue'
import ChatPersonalizationSettings from './settings/ChatPersonalizationSettings.vue'

defineProps({ modelValue: { type: Boolean, default: false } })
defineEmits(['update:modelValue'])

const activeTab = ref('appearance')
const { preferences, saving, save, reset } = useChatPreferences()
const tabs = [{ key: 'appearance', label: '外观' }, { key: 'personalization', label: '个性化' }, { key: 'general', label: '通用' }]

const handleSave = async () => {
  if (await save()) ElMessage.success('设置已保存')
  else ElMessage.error('设置保存失败，请稍后重试')
}

const handleReset = async () => {
  try {
    await ElMessageBox.confirm('将恢复默认主题和个性化设置，确定继续吗？', '重置设置', { type: 'warning' })
    if (await reset()) ElMessage.success('已恢复默认设置')
  } catch { /* 用户取消 */ }
}
</script>

<style lang="scss" scoped>
.settings-layout { display: flex; min-height: 520px; margin: -8px -12px 0; }
.settings-nav { width: 150px; flex: 0 0 150px; padding: 8px; border-right: 1px solid #e5e7eb; }
.settings-nav button { width: 100%; border: 0; background: transparent; padding: 10px 12px; text-align: left; border-radius: 8px; cursor: pointer; font-size: 14px; color: #4b5563; }
.settings-nav button:hover, .settings-nav button.active { background: #f0fdf4; color: #047857; font-weight: 600; }
.settings-content { flex: 1; min-width: 0; overflow-y: auto; padding: 8px 22px 16px; }
.footer-spacer { flex: 1; }
:global(.el-dialog) { background: var(--chat-canvas); color: var(--chat-ink); }
:global(.el-dialog__title), :global(.el-dialog__body) { color: var(--chat-ink); }
:global(.el-dialog__header), :global(.el-dialog__footer) { border-color: var(--chat-hairline); }
@media (max-width: 620px) { .settings-layout { min-height: 0; }.settings-nav { width: 92px; flex-basis: 92px; }.settings-content { padding: 8px 12px; }.color-grid { grid-template-columns: repeat(2, 1fr); }.radius-grid { grid-template-columns: repeat(3, 1fr); } }
</style>
