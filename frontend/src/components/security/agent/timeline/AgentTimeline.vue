<template>
  <div class="agent-timeline">
    <TimelineSkeleton v-if="loading && !items.length" />
    <div v-else-if="!items.length" class="agent-timeline__empty">
      暂无时间线事件
    </div>
    <div v-else class="agent-timeline__list">
      <AgentTimelineItem
        v-for="item in items"
        :key="item.publicId"
        :item="item"
      />
    </div>
  </div>
</template>

<script setup>
import AgentTimelineItem from './AgentTimelineItem.vue'
import TimelineSkeleton from './TimelineSkeleton.vue'

defineProps({
  items: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false }
})
</script>

<style scoped lang="scss">
.agent-timeline {
  min-height: 60px;
}

.agent-timeline__empty {
  padding: 20px 0;
  text-align: center;
  font-size: 13px;
  color: var(--chat-hollow, #8494a8);
}

.agent-timeline__list {
  display: flex;
  flex-direction: column;
}
</style>
