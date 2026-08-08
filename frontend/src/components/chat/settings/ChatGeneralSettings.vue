<template>
  <div class="settings-section">
    <h2>通用设置</h2><p class="section-help">管理语言和聊天行为。</p>
    <label for="language">语言</label>
    <select id="language" v-model="modelValue.language" class="wide-select"><option v-for="item in languages" :key="item.value" :value="item.value">{{ item.label }}</option></select>
    <label class="switch-row"><input type="checkbox" checked disabled><span>保存聊天记录</span></label>
    <label class="switch-row"><input type="checkbox" checked disabled><span>Enter 发送消息</span></label>
    <p class="section-note">语言切换会先应用于 AI 安全助手和设置中心，其他页面将逐步接入。</p>
  </div>
</template>

<script setup>
defineProps({ modelValue: { type: Object, required: true } })
const languages = [{ value: 'zh-CN', label: '简体中文' }, { value: 'en', label: 'English' }, { value: 'fr', label: 'Français' }, { value: 'ru', label: 'Русский' }, { value: 'ja', label: '日本語' }, { value: 'vi', label: 'Tiếng Việt' }, { value: 'zh-TW', label: '繁體中文' }]
</script>

<style scoped>
.settings-section h2 { margin: 0; font-size: 21px; color: var(--chat-ink); }
.section-help,
.section-note { margin: 6px 0 22px; color: var(--chat-hollow); font-size: 13px; line-height: 1.6; }
.settings-section label:not(.switch-row) {
  display: block;
  margin: 16px 0 6px;
  color: var(--chat-muted);
  font-size: 13px;
  font-weight: 600;
}
.wide-select {
  min-width: 180px;
  padding: 8px;
  border: 1px solid var(--chat-hairline-strong);
  border-radius: 6px;
  background: var(--chat-field);
  color: var(--chat-ink);
}
.switch-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 16px;
  color: var(--chat-muted);
  font-size: 13px;
}
</style>
