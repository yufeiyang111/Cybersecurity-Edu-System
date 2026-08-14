<template>
  <div v-if="shouldRender" class="chat-thinking">
    <button
      class="ct-toggle"
      :class="{ open }"
      type="button"
      @click="open = !open"
    >
      <BaseIcon name="chevron-down" :size="13" />
      <span>{{ seconds !== null ? t('thinking.seconds', { seconds }) : t('thinking.title') }}</span>
    </button>
    <div v-if="open" class="ct-panel">
      <div v-if="reasoning" class="ct-reasoning">{{ reasoning }}</div>
      <template v-else>
        <div v-if="citationCount > 0" class="ct-row">
          <span class="ct-label">可核验引用</span>
          <span>{{ citationCount }} 条</span>
        </div>
        <div v-if="modelName" class="ct-row">
          <span class="ct-label">{{ t('thinking.model') }}</span>
          <span>{{ modelName }}</span>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { BaseIcon } from '@/components/ui'
import { useI18n } from '@/features/chat/i18n'

const props = defineProps({
  seconds: { type: Number, default: null },
  citationCount: { type: Number, default: 0 },
  modelName: { type: String, default: '' },
  reasoning: { type: String, default: '' }
})

const open = ref(false)
const { t } = useI18n()

const shouldRender = computed(() => {
  return props.seconds !== null || props.reasoning || props.citationCount > 0
})
</script>

<style scoped lang="scss">
.chat-thinking {
  margin-bottom: 6px;
}

.ct-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 0;
  border: 0;
  color: var(--chat-hollow);
  background: transparent;
  font: inherit;
  font-size: calc(13px * var(--chat-font-scale));
  cursor: pointer;
  user-select: none;

  .ui-icon {
    transition: transform 0.15s;
  }

  &.open .ui-icon {
    transform: rotate(180deg);
  }

  &:focus-visible {
    outline: 2px solid var(--chat-link);
    outline-offset: 2px;
  }
}

.ct-panel {
  margin-top: 4px;
  padding: 2px 0 2px 14px;
  border-left: 2px solid var(--chat-hairline);
}

.ct-reasoning {
  color: var(--chat-hollow);
  font-size: calc(13px * var(--chat-font-scale));
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
}

.ct-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  color: var(--chat-hollow);
  font-size: calc(13px * var(--chat-font-scale));
  line-height: 1.7;
}

.ct-label {
  flex-shrink: 0;
}
</style>