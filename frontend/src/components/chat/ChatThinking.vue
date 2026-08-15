<template>
  <section
    v-if="shouldRender"
    class="chat-thinking"
    :data-mode="mode"
  >
    <button
      class="ct-toggle"
      :class="{ open }"
      type="button"
      @click="toggle"
    >
      <BaseIcon name="chevron-down" :size="13" />
      <span>{{ title }}</span>
    </button>
    <div
      v-if="open"
      class="ct-panel"
    >
      <div
        v-if="hasReasoning"
        class="ct-reasoning"
      >
        {{ reasoning }}
      </div>
      <template v-else>
        <p class="ct-note">模型未返回可展示推理，以下为本次回答的受控执行过程。</p>
        <div
          v-for="step in ragProcess.steps"
          :key="step.label"
          class="ct-row"
        >
          <span class="ct-label">{{ step.label }}</span>
          <span>{{ step.detail }}</span>
        </div>
      </template>
    </div>
  </section>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { BaseIcon } from '@/components/ui'

const props = defineProps({
  seconds: { type: Number, default: null },
  reasoning: { type: String, default: '' },
  ragProcess: { type: Object, default: null }
})

const open = ref(false)
const userToggled = ref(false)

const hasReasoning = computed(() => {
  return typeof props.reasoning === 'string' && props.reasoning.trim().length > 0
})

const hasProcess = computed(() => {
  return Array.isArray(props.ragProcess?.steps) && props.ragProcess.steps.length > 0
})

const mode = computed(() => {
  return hasReasoning.value ? 'reasoning' : 'process'
})

const title = computed(() => {
  const duration = Number.isFinite(props.seconds)
    ? ` · ${props.seconds.toFixed(1)} 秒`
    : ''
  return hasReasoning.value
    ? `模型推理${duration}`
    : `检索与生成过程${duration}`
})

const shouldRender = computed(() => {
  return hasReasoning.value || hasProcess.value
})

const toggle = () => {
  userToggled.value = true
  open.value = !open.value
}

watch(
  [hasReasoning, hasProcess],
  ([reasoningAvailable, processAvailable], [previousReasoning, previousProcess]) => {
    const becameAvailable = (!previousReasoning && reasoningAvailable)
      || (!previousProcess && processAvailable)
    if (becameAvailable && !userToggled.value) {
      open.value = true
    }
  }
)
</script>

<style scoped lang="scss">
.chat-thinking {
  margin-bottom: 8px;
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
  padding: 8px 10px;
  border-left: 2px solid var(--chat-hairline);
  border-radius: 0 7px 7px 0;
  background: var(--chat-bubble);
}

.ct-reasoning {
  color: var(--chat-muted);
  font-size: calc(13px * var(--chat-font-scale));
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
}

.ct-note {
  margin: 0 0 7px;
  color: var(--chat-hollow);
  font-size: calc(12px * var(--chat-font-scale));
  line-height: 1.55;
}

.ct-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 3px 0;
  color: var(--chat-muted);
  font-size: calc(12px * var(--chat-font-scale));
  line-height: 1.55;
}

.ct-label {
  flex-shrink: 0;
  color: var(--chat-hollow);
}

@media (max-width: 767px) {
  .ct-panel {
    padding: 8px 9px;
  }
}
</style>