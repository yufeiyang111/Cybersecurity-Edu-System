<template>
  <div class="settings-section">
    <h2>主题设置</h2><p class="section-help">调整外观和布局以适应你的偏好。</p>
    <h3>主题</h3>
    <div class="choice-grid theme-grid">
      <button v-for="item in themes" :key="item.value" class="choice-card" :class="[{ selected: modelValue.theme === item.value }, `theme-${item.value}`]" @click="modelValue.theme = item.value">
        <span class="theme-preview"><i></i><b></b><em></em></span><span>{{ item.label }}</span>
      </button>
    </div>
    <h3>颜色预设</h3>
    <div class="choice-grid color-grid">
      <button v-for="item in presets" :key="item.value" class="color-choice" :class="[{ selected: modelValue.color_preset === item.value }, `preset-${item.value}`]" @click="modelValue.color_preset = item.value">
        <span class="color-swatch"></span><span>{{ item.label }}</span>
      </button>
    </div>
    <h3>字体</h3>
    <div class="choice-grid font-grid">
      <button v-for="item in fonts" :key="item.value" class="font-choice" :class="{ selected: modelValue.font_family === item.value }" @click="modelValue.font_family = item.value"><strong :class="`font-${item.value}`">Aa</strong><span>{{ item.label }}</span></button>
    </div>
    <h3>圆角</h3>
    <div class="radius-grid">
      <button v-for="item in radii" :key="item.value" class="radius-choice" :class="{ selected: modelValue.border_radius === item.value }" @click="modelValue.border_radius = item.value"><span :style="{ borderRadius: item.css }"></span><small>{{ item.label }}</small></button>
    </div>
    <h3>布局</h3>
    <div class="inline-options">
      <label>内容密度 <select v-model="modelValue.content_density"><option value="compact">紧凑</option><option value="standard">标准</option><option value="comfortable">宽松</option></select></label>
      <label>内容宽度 <select v-model="modelValue.content_width"><option value="narrow">窄</option><option value="standard">标准</option><option value="wide">宽</option></select></label>
    </div>
  </div>
</template>

<script setup>
defineProps({ modelValue: { type: Object, required: true } })
const themes = [
  { value: 'system', label: '系统' },
  { value: 'light', label: '浅色' },
  { value: 'dark', label: '深色' },
  { value: 'sepia', label: '米黄护眼' }
]
const presets = [
  { value: 'default', label: '默认' }, { value: 'anthropic', label: 'Anthropic' }, { value: 'simple', label: '超大字体简易' },
  { value: 'night', label: '暗夜' }, { value: 'rose', label: '玫瑰花园' }, { value: 'lake', label: '湖光' }, { value: 'sunset', label: '日落霞光' },
  { value: 'forest', label: '森林低语' }, { value: 'sea', label: '海风' }, { value: 'lavender', label: '薰衣草梦' },
  { value: 'emerald', label: '翡翠' }, { value: 'gold', label: '鎏金' }, { value: 'candy', label: '糖果' }
]
const fonts = [{ value: 'auto', label: 'Auto' }, { value: 'sans', label: 'Sans' }, { value: 'serif', label: 'Serif' }]
const radii = [{ value: 'auto', label: 'Auto', css: '10px' }, { value: '0', label: '0', css: '0' }, { value: '0.3', label: '0.3', css: '3px' }, { value: '0.5', label: '0.5', css: '5px' }, { value: '0.75', label: '0.75', css: '8px' }, { value: '1.0', label: '1.0', css: '12px' }]
</script>

<style scoped>
.settings-section h2 { margin: 0; font-size: 21px; color: var(--chat-ink); }
.section-help { margin: 6px 0 22px; color: var(--chat-hollow); font-size: 13px; }
.settings-section h3 { margin: 22px 0 10px; font-size: 15px; color: var(--chat-ink); }
.choice-grid { display: grid; gap: 10px; }
.theme-grid { grid-template-columns: repeat(3, 1fr); }
.choice-card,
.color-choice,
.font-choice,
.radius-choice {
  position: relative;
  border: 1px solid var(--chat-hairline-strong);
  background: var(--chat-field);
  cursor: pointer;
  color: var(--chat-ink);
}
.choice-card { padding: 8px; border-radius: 8px; text-align: left; }
.choice-card.selected,
.color-choice.selected,
.font-choice.selected,
.radius-choice.selected {
  border-color: var(--chat-accent);
  box-shadow: 0 0 0 1px var(--chat-accent);
  background: var(--chat-accent-soft);
}
.theme-preview {
  display: block;
  height: 70px;
  padding: 8px;
  background: var(--chat-field);
  border-radius: 5px;
}
.theme-preview i,
.theme-preview b,
.theme-preview em {
  display: block;
  height: 6px;
  margin: 0 0 7px;
  border-radius: 2px;
  background: var(--chat-hairline-strong);
}
.theme-preview i { width: 35%; height: 45px; float: left; margin-right: 8px; background: var(--chat-bubble); }
.theme-preview b { width: 46%; background: var(--chat-hollow); opacity: .55; }
.theme-preview em { width: 65%; background: var(--chat-hairline-strong); }
/* 深色主题预览固定用深色示意，不随当前主题变色 */
.theme-dark .theme-preview { background: #0f172a; }
.theme-dark .theme-preview i { background: #1e3a5f; }
.theme-dark .theme-preview b { background: #315b8d; }
/* 米黄护眼主题预览固定用暖色示意 */
.theme-sepia .theme-preview { background: #fbf3e0; }
.theme-sepia .theme-preview i { background: #e8dcbf; }
.theme-sepia .theme-preview b { background: #d8c9a6; }
.choice-card > span:last-child,
.color-choice > span:last-child,
.font-choice > span:last-child,
.radius-choice small {
  display: block;
  margin-top: 7px;
  text-align: center;
  font-size: 12px;
}
.color-grid { grid-template-columns: repeat(5, 1fr); }
.color-choice { padding: 6px; border-radius: 8px; }
.color-swatch {
  display: block;
  height: 42px;
  border-radius: 5px;
  background: linear-gradient(135deg, #f59e0b, #06b6d4, #8b5cf6);
}
.preset-anthropic .color-swatch { background: linear-gradient(135deg, #f8d0c1, #eb8262); }
.preset-simple .color-swatch { background: linear-gradient(135deg, #111, #eee); }
.preset-night .color-swatch { background: linear-gradient(135deg, #343044, #8b6d8a); }
.preset-rose .color-swatch { background: linear-gradient(135deg, #e11d48, #fb7185); }
.preset-lake .color-swatch { background: linear-gradient(135deg, #06b6a0, #0f8e8b); }
.preset-sunset .color-swatch { background: linear-gradient(135deg, #d94841, #fb9970); }
.preset-forest .color-swatch { background: linear-gradient(135deg, #0f766e, #3d5c75); }
.preset-sea .color-swatch { background: #4967eb; }
.preset-lavender .color-swatch { background: linear-gradient(135deg, #8b5fc5, #9bd4d4); }
.preset-emerald .color-swatch { background: linear-gradient(135deg, #10b981, #047857); }
.preset-gold .color-swatch { background: linear-gradient(135deg, #f59e0b, #b45309); }
.preset-candy .color-swatch { background: linear-gradient(135deg, #f472b6, #ec4899); }
.font-grid { grid-template-columns: repeat(3, 1fr); }
.font-choice { padding: 12px; border-radius: 8px; }
.font-choice strong { display: block; text-align: center; font-size: 26px; }
.font-sans { font-family: Arial, sans-serif; }
.font-serif { font-family: Georgia, serif; }
.radius-grid { display: grid; grid-template-columns: repeat(6, 1fr); gap: 8px; }
.radius-choice { padding: 9px 5px 6px; border-radius: 8px; }
.radius-choice span {
  display: block;
  height: 32px;
  border: 2px solid var(--chat-hollow);
  background: var(--chat-field);
}
.inline-options { display: flex; gap: 16px; flex-wrap: wrap; }
.inline-options label {
  display: flex;
  flex-direction: column;
  gap: 6px;
  color: var(--chat-muted);
  font-size: 13px;
}
.inline-options select {
  min-width: 150px;
  padding: 8px;
  border: 1px solid var(--chat-hairline-strong);
  border-radius: 6px;
  background: var(--chat-field);
  color: var(--chat-ink);
}
@media (max-width: 620px) {
  .color-grid { grid-template-columns: repeat(2, 1fr); }
  .radius-grid { grid-template-columns: repeat(3, 1fr); }
}
</style>
