<template>
  <section
    v-if="warnings.length"
    class="warning-block"
    aria-live="polite"
  >
    <span
      class="wb-icon"
      aria-hidden="true"
    >
      ⚠
    </span>
    <div class="wb-body">
      <span class="wb-label">运行提示</span>
      <ul class="wb-list">
        <li
          v-for="warning in warnings"
          :key="warning.title + warning.detail"
          class="wb-item"
        >
          <strong>{{ warning.title }}</strong>
          <p>{{ warning.detail }}</p>
        </li>
      </ul>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { presentAgentWarnings } from '@/features/security/agent/warningPresentation'

const props = defineProps({
  codes: {
    type: Array,
    default: () => []
  }
})

const warnings = computed(() => presentAgentWarnings(props.codes))
</script>

<style scoped lang="scss">
.warning-block {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 14px;
  border: 1px solid var(--chat-warning-border);
  border-radius: var(--chat-radius);
  background: var(--chat-warning-bg);
}

.wb-icon {
  flex: none;
  color: var(--chat-warning-ink);
  font-size: 14px;
  line-height: 1.5;
}

.wb-body {
  flex: 1;
  min-width: 0;
}

.wb-label {
  display: block;
  margin-bottom: 5px;
  color: var(--chat-warning-ink);
  font-size: 12px;
  font-weight: 600;
}

.wb-list {
  display: grid;
  gap: 7px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.wb-item {
  color: var(--chat-warning-ink);
  font-size: 12px;
  line-height: 1.55;
}

.wb-item strong {
  font-weight: 600;
}

.wb-item p {
  margin: 2px 0 0;
  color: var(--chat-muted);
}
</style>
