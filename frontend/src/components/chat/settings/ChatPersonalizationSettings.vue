<template>
  <div class="settings-section">
    <h2>个性化</h2><p class="section-help">告诉 AI 你的背景和偏好的回答方式。</p>
    <label for="about-user">关于我</label><textarea id="about-user" v-model="modelValue.about_user" maxlength="1000" placeholder="例如：我是一名负责 Web 安全的开发工程师。"></textarea>
    <label for="response-preferences">希望 AI 如何回答</label><textarea id="response-preferences" v-model="modelValue.response_preferences" maxlength="2000" placeholder="例如：先给结论，再给原因和修复步骤。"></textarea>
    <label for="custom-prompt">自定义提示词</label><textarea id="custom-prompt" v-model="modelValue.custom_prompt" maxlength="4000" placeholder="补充你的长期回答偏好。系统安全指令始终优先。"></textarea>
    <label for="response-style">回答风格</label>
    <select id="response-style" v-model="modelValue.response_style" class="wide-select"><option value="professional">专业</option><option value="concise">简洁</option><option value="teaching">教学</option><option value="analytical">分析型</option></select>
    <label class="switch-row"><input v-model="modelValue.show_citations" type="checkbox"><span>默认展示知识来源</span></label>
    <label class="switch-row"><input v-model="modelValue.show_security_warnings" type="checkbox"><span>默认展示安全警告</span></label>
  </div>
</template>

<script setup>
defineProps({ modelValue: { type: Object, required: true } })
</script>

<style scoped>
.settings-section h2 { margin: 0; font-size: 21px; color: var(--chat-ink); }
.section-help { margin: 6px 0 22px; color: var(--chat-hollow); font-size: 13px; }
.settings-section label:not(.switch-row) {
  display: block;
  margin: 16px 0 6px;
  color: var(--chat-muted);
  font-size: 13px;
  font-weight: 600;
}
.settings-section textarea {
  display: block;
  width: 100%;
  min-height: 78px;
  box-sizing: border-box;
  resize: vertical;
  padding: 10px;
  border: 1px solid var(--chat-hairline-strong);
  border-radius: 7px;
  font: inherit;
  background: var(--chat-field);
  color: var(--chat-ink);
}
.wide-select {
  min-width: 150px;
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
