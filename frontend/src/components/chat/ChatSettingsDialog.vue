<template>
  <el-dialog
    :model-value="modelValue"
    :title="t('settings.title')"
    width="min(760px, calc(100vw - 32px))"
    class="chat-settings-dialog"
    destroy-on-close
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <div class="settings-layout">
      <nav class="settings-nav" aria-label="设置分类">
        <button v-for="tab in tabs" :key="tab.key" :class="{ active: activeTab === tab.key }" @click="activeTab = tab.key">
          {{ t(tab.labelKey) }}
        </button>
      </nav>

      <section class="settings-content">
        <ChatAppearanceSettings v-if="activeTab === 'appearance'" v-model="preferences" />
        <ChatPersonalizationSettings v-else-if="activeTab === 'personalization'" v-model="preferences" />
        <ChatMemorySettings v-else-if="activeTab === 'memory'" />
        <ChatGeneralSettings v-else v-model="preferences" />
      </section>
    </div>
    <template #footer>
      <el-button type="danger" plain @click="handleReset">{{ t('settings.reset') }}</el-button>
      <span class="footer-spacer"></span>
      <el-button @click="$emit('update:modelValue', false)">{{ t('settings.cancel') }}</el-button>
      <el-button type="primary" :loading="saving" @click="handleSave">{{ t('settings.save') }}</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useChatPreferences } from '@/composables/chat/useChatPreferences'
import { useI18n } from '@/features/chat/i18n'
import ChatAppearanceSettings from './settings/ChatAppearanceSettings.vue'
import ChatGeneralSettings from './settings/ChatGeneralSettings.vue'
import ChatMemorySettings from './settings/ChatMemorySettings.vue'
import ChatPersonalizationSettings from './settings/ChatPersonalizationSettings.vue'

defineProps({ modelValue: { type: Boolean, default: false } })
defineEmits(['update:modelValue'])

const activeTab = ref('appearance')
const { preferences, saving, save, reset } = useChatPreferences()
const { t } = useI18n()
const tabs = [
  { key: 'appearance', labelKey: 'settings.appearance' },
  { key: 'personalization', labelKey: 'settings.personalization' },
  { key: 'memory', labelKey: 'settings.memory' },
  { key: 'general', labelKey: 'settings.general' }
]

const handleSave = async () => {
  if (await save()) ElMessage.success(t('settings.saved'))
  else ElMessage.error(t('settings.saveFailed'))
}

const handleReset = async () => {
  try {
    await ElMessageBox.confirm(t('settings.resetConfirm'), t('settings.resetTitle'), { type: 'warning' })
    if (await reset()) ElMessage.success(t('settings.resetDone'))
  } catch { /* 用户取消 */ }
}
</script>

<style lang="scss" scoped>
.settings-layout { display: flex; min-height: 520px; margin: -8px -12px 0; }
.settings-nav {
  width: 150px;
  flex: 0 0 150px;
  padding: 8px;
  border-right: 1px solid var(--chat-hairline);
}
.settings-nav button {
  width: 100%;
  border: 0;
  background: transparent;
  padding: 10px 12px;
  text-align: left;
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
  color: var(--chat-muted);

  &:hover {
    background: var(--chat-hover);
  }

  &.active {
    background: var(--chat-accent-soft);
    color: var(--chat-accent);
    font-weight: 600;
  }
}
.settings-content { flex: 1; min-width: 0; overflow-y: auto; padding: 8px 22px 16px; }
.footer-spacer { flex: 1; }
// 弹窗背景/文字/边框由 chat-tokens.scss 的 --el-* 暗色变量控制，这里不再重复覆盖
@media (max-width: 620px) {
  .settings-layout { min-height: 0; }
  .settings-nav { width: 92px; flex-basis: 92px; }
  .settings-content { padding: 8px 12px; }
  .color-grid { grid-template-columns: repeat(2, 1fr); }
  .radius-grid { grid-template-columns: repeat(3, 1fr); }
}
</style>
