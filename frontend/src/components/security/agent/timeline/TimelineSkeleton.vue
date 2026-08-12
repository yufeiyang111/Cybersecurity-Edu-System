<template>
  <div class="timeline-skeleton" aria-busy="true">
    <div
      v-for="index in rows"
      :key="index"
      class="timeline-skeleton__row"
    >
      <div class="timeline-skeleton__avatar" />
      <div class="timeline-skeleton__lines">
        <div class="timeline-skeleton__line" />
        <div class="timeline-skeleton__line timeline-skeleton__line--short" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps({
  rows: { type: Number, default: 4 }
})

const rows = ref(props.rows)
</script>

<style scoped lang="scss">
.timeline-skeleton {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 12px 0;
}

.timeline-skeleton__row {
  display: flex;
  gap: 10px;
  align-items: flex-start;
}

.timeline-skeleton__avatar {
  width: 26px;
  height: 26px;
  border-radius: 999px;
  background: var(--chat-hover, #eef2f7);
  flex: none;
}

.timeline-skeleton__lines {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.timeline-skeleton__line {
  height: 12px;
  border-radius: 4px;
  background: var(--chat-hover, #eef2f7);
}

.timeline-skeleton__line--short {
  width: 55%;
}
</style>
