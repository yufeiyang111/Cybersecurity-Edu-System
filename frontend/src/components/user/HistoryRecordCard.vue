<template>
  <article class="user-card history-card">
    <div class="history-card__main">
      <div class="history-card__head">
        <span class="history-card__icon">
          <BaseIcon name="history" :size="16" />
        </span>
        <div class="history-card__question">
          {{ record.question }}
        </div>
      </div>

      <div v-if="answerPreview" class="history-card__answer">
        {{ answerPreview }}
      </div>

      <div v-if="sources.length" class="history-card__sources">
        <span v-for="(s, idx) in sources" :key="idx" class="history-card__source">
          {{ s.title || s.id }}
        </span>
      </div>
    </div>

    <div class="history-card__foot">
      <div class="history-card__meta">
        <span v-if="record.response_time" class="meta-item">
          <BaseIcon name="clock" :size="13" />
          {{ record.response_time.toFixed(2) }}s
        </span>
        <span v-if="record.model_name" class="meta-item">
          {{ record.model_name }}
        </span>
        <span v-if="sources.length" class="meta-item">
          <BaseIcon name="layers" :size="13" />
          {{ sources.length }} 个来源
        </span>
      </div>

      <div class="history-card__actions">
        <span
          v-if="record.feedback"
          class="feedback-badge"
          :class="`feedback-badge--${record.feedback}`"
        >
          {{ feedbackText }}
        </span>
        <button
          type="button"
          class="row-btn"
          @click="$emit('view', record)"
        >
          <BaseIcon name="eye" :size="14" />
          查看
        </button>
        <button
          type="button"
          class="row-btn row-btn--primary"
          @click="$emit('continue', record)"
        >
          <BaseIcon name="play" :size="14" />
          继续问
        </button>
      </div>
    </div>
  </article>
</template>

<script setup>
import { computed } from 'vue'
import { BaseIcon } from '@/components/ui'

const props = defineProps({
  record: { type: Object, required: true }
})

defineEmits(['view', 'continue'])

const feedbackText = computed(() => {
  const texts = { good: '满意', neutral: '一般', bad: '不满意' }
  return texts[props.record.feedback] || ''
})

const answerPreview = computed(() => {
  const answer = props.record.answer
  if (!answer) return ''
  return answer.length > 160 ? answer.substring(0, 160) + '...' : answer
})

const sources = computed(() => {
  return Array.isArray(props.record.sources) ? props.record.sources : []
})
</script>

<style lang="scss" scoped>
@use '@/styles/user-vars' as *;
@use '@/styles/user-cards' as *;

.history-card {
  cursor: pointer;
}

.history-card__main {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
}

.history-card__head {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  min-width: 0;
}

.history-card__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  flex-shrink: 0;
  border-radius: 7px;
  background: $brand-light;
  color: $brand-color;
}

.history-card__question {
  font-size: 14px;
  font-weight: 600;
  color: $text-primary;
  line-height: 1.6;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  word-break: break-word;
}

.history-card__answer {
  padding-left: 38px;
  font-size: 13px;
  color: $text-regular;
  line-height: 1.7;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
  word-break: break-word;
}

.history-card__sources {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  padding-left: 38px;
}

.history-card__source {
  padding: 2px 8px;
  border-radius: 999px;
  background: $bg-inset;
  color: $text-secondary;
  font-size: 11px;
}

.history-card__foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding-top: 10px;
  border-top: 1px solid $border-lighter;
  flex-wrap: wrap;
}

.history-card__meta {
  display: flex;
  align-items: center;
  gap: 14px;
  color: $text-placeholder;
  font-size: 12px;
  flex-wrap: wrap;
}

.meta-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.history-card__actions {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: auto;
}
</style>
