<template>
  <div class="settings-section">
    <h2>{{ t('appearance.title') }}</h2>
    <p class="section-help">{{ t('appearance.help') }}</p>

    <h3>{{ t('appearance.colors') }}</h3>
    <div class="choice-grid theme-grid">
      <button
        v-for="item in themes"
        :key="item.value"
        class="choice-card"
        :class="[{ selected: modelValue.theme === item.value }, `theme-${item.value}`]"
        @click="modelValue.theme = item.value"
      >
        <span class="theme-preview"><i></i><b></b><em></em></span>
        <span>{{ t(item.labelKey) }}</span>
      </button>
    </div>
    <div class="choice-grid color-grid">
      <button
        v-for="item in presets"
        :key="item.value"
        class="color-choice"
        :class="[{ selected: modelValue.color_preset === item.value }, `preset-${item.value}`]"
        :title="t(item.labelKey)"
        @click="modelValue.color_preset = item.value"
      >
        <span class="color-swatch"></span>
        <span>{{ t(item.labelKey) }}</span>
      </button>
    </div>

    <h3>{{ t('appearance.font') }}</h3>
    <div class="choice-grid font-grid">
      <button
        v-for="item in fonts"
        :key="item.value"
        class="font-choice"
        :class="{ selected: modelValue.font_family === item.value }"
        @click="modelValue.font_family = item.value"
      >
        <strong :class="`font-${item.value}`">Aa</strong>
        <span>{{ item.label }}</span>
      </button>
    </div>

    <h3>{{ t('appearance.fontSize') }}</h3>
    <div class="choice-grid fontsize-grid">
      <button
        v-for="item in sizes"
        :key="item.value"
        class="fontsize-choice"
        :class="{ selected: modelValue.font_size === item.value }"
        @click="modelValue.font_size = item.value"
      >
        <strong :class="`fontsize-${item.value}`">Aa</strong>
        <span>{{ t(item.labelKey) }}</span>
      </button>
    </div>

    <h3>{{ t('appearance.radius') }}</h3>
    <div class="radius-grid">
      <button
        v-for="item in radii"
        :key="item.value"
        class="radius-choice"
        :class="{ selected: modelValue.border_radius === item.value }"
        @click="modelValue.border_radius = item.value"
      >
        <span :style="{ borderRadius: item.css }"></span>
        <small>{{ item.label }}</small>
      </button>
    </div>

    <h3>{{ t('appearance.layout') }}</h3>
    <div class="inline-options">
      <label>
        {{ t('appearance.density') }}
        <select v-model="modelValue.content_density">
          <option value="compact">{{ t('appearance.densityCompact') }}</option>
          <option value="standard">{{ t('appearance.densityStandard') }}</option>
          <option value="comfortable">{{ t('appearance.densityComfortable') }}</option>
        </select>
      </label>
      <label>
        {{ t('appearance.width') }}
        <select v-model="modelValue.content_width">
          <option value="narrow">{{ t('appearance.widthNarrow') }}</option>
          <option value="standard">{{ t('appearance.widthStandard') }}</option>
          <option value="wide">{{ t('appearance.widthWide') }}</option>
        </select>
      </label>
    </div>
  </div>
</template>

<script setup>
import { useI18n } from '@/features/chat/i18n'

defineProps({ modelValue: { type: Object, required: true } })
const { t } = useI18n()

const themes = [
  { value: 'system', labelKey: 'appearance.themeSystem' },
  { value: 'light', labelKey: 'appearance.themeLight' },
  { value: 'dark', labelKey: 'appearance.themeDark' },
  { value: 'sepia', labelKey: 'appearance.themeSepia' }
]
const presets = [
  { value: 'default', labelKey: 'appearance.presetDefault' },
  { value: 'anthropic', labelKey: 'appearance.presetAnthropic' },
  { value: 'simple', labelKey: 'appearance.presetSimple' },
  { value: 'night', labelKey: 'appearance.presetNight' },
  { value: 'rose', labelKey: 'appearance.presetRose' },
  { value: 'lake', labelKey: 'appearance.presetLake' },
  { value: 'sunset', labelKey: 'appearance.presetSunset' },
  { value: 'forest', labelKey: 'appearance.presetForest' },
  { value: 'sea', labelKey: 'appearance.presetSea' },
  { value: 'lavender', labelKey: 'appearance.presetLavender' },
  { value: 'emerald', labelKey: 'appearance.presetEmerald' },
  { value: 'gold', labelKey: 'appearance.presetGold' },
  { value: 'candy', labelKey: 'appearance.presetCandy' }
]
const fonts = [
  { value: 'auto', label: 'Auto' },
  { value: 'sans', label: 'Sans' },
  { value: 'serif', label: 'Serif' }
]
const sizes = [
  { value: 'small', labelKey: 'appearance.fontSizeSmall' },
  { value: 'medium', labelKey: 'appearance.fontSizeMedium' },
  { value: 'large', labelKey: 'appearance.fontSizeLarge' }
]
const radii = [
  { value: 'auto', label: 'Auto', css: '10px' },
  { value: '0', label: '0', css: '0' },
  { value: '0.3', label: '0.3', css: '3px' },
  { value: '0.5', label: '0.5', css: '5px' },
  { value: '0.75', label: '0.75', css: '8px' },
  { value: '1.0', label: '1.0', css: '12px' }
]
</script>

<style scoped>
.settings-section h2 { margin: 0; font-size: 21px; color: var(--chat-ink); }
.section-help { margin: 6px 0 22px; color: var(--chat-hollow); font-size: 13px; }
.settings-section h3 { margin: 22px 0 10px; font-size: 15px; color: var(--chat-ink); }
.choice-grid { display: grid; gap: 10px; }
.theme-grid { grid-template-columns: repeat(4, 1fr); }
.choice-card,
.color-choice,
.font-choice,
.fontsize-choice,
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
.fontsize-choice.selected,
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
.fontsize-choice > span:last-child,
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
.fontsize-grid { grid-template-columns: repeat(3, 1fr); }
.fontsize-choice { padding: 12px; border-radius: 8px; }
.fontsize-choice strong { display: block; text-align: center; font-size: 22px; }
.fontsize-small { font-size: 16px; }
.fontsize-large { font-size: 28px; }
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
  .theme-grid { grid-template-columns: repeat(2, 1fr); }
  .color-grid { grid-template-columns: repeat(2, 1fr); }
  .radius-grid { grid-template-columns: repeat(3, 1fr); }
}
</style>
