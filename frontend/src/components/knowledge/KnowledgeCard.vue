<template>
  <article
    class="knowledge-card"
    :style="{ '--kb-delay': `${delay}ms` }"
    @click="$emit('click')"
  >
    <div class="card-head">
      <span class="pill pill-cat">{{ item.category_name || '未分类' }}</span>
      <span class="pill" :class="difficultyClass">
        {{ difficultyText }}
      </span>
      <span class="card-more" aria-hidden="true">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M5 12h14" />
          <path d="M13 6l6 6-6 6" />
        </svg>
      </span>
    </div>
    <h3 class="card-title">{{ item.title }}</h3>
    <p class="card-summary">{{ item.summary || '暂无摘要' }}</p>
    <footer class="card-foot">
      <div v-if="item.tags?.length" class="card-kws">
        <span v-for="tag in item.tags.slice(0, 3)" :key="tag" class="kw">
          {{ tag }}
        </span>
      </div>
      <div class="card-meta">
        <span class="meta-item">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
            <circle cx="12" cy="12" r="3" />
          </svg>
          {{ item.view_count }}
        </span>
        <span class="meta-item">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 2l3.1 6.3 6.9 1-5 4.9 1.2 6.8L12 17.8 5.8 21l1.2-6.8-5-4.9 6.9-1z" />
          </svg>
          {{ item.favorite_count }}
        </span>
      </div>
    </footer>
  </article>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  item: {
    type: Object,
    required: true
  },
  delay: {
    type: Number,
    default: 0
  }
})

defineEmits(['click'])

const difficultyText = computed(() => {
  const texts = { easy: '入门', medium: '进阶', hard: '高级' }
  return texts[props.item.difficulty] || '普通'
})

const difficultyClass = computed(() => {
  const classes = { easy: 'pill-easy', medium: 'pill-mid', hard: 'pill-hard' }
  return classes[props.item.difficulty] || 'pill-none'
})
</script>

<style lang="scss" scoped>
.knowledge-card {
  position: relative;
  display: flex;
  flex-direction: column;
  background: #fff;
  border: 1px solid #d8dee4;
  border-radius: 12px;
  padding: 20px;
  cursor: pointer;
  overflow: hidden;
  transition:
    transform 0.35s cubic-bezier(0.22, 1, 0.36, 1),
    box-shadow 0.35s cubic-bezier(0.22, 1, 0.36, 1),
    border-color 0.35s;
  animation: kbCardIn 0.6s cubic-bezier(0.22, 1, 0.36, 1) both;
  animation-delay: var(--kb-delay);
}

.knowledge-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: linear-gradient(90deg, #2ea44f, #4fd66e);
  transform: scaleX(0);
  transform-origin: left;
  transition: transform 0.4s cubic-bezier(0.22, 1, 0.36, 1);
}

.knowledge-card:hover {
  border-color: rgba(46, 164, 79, 0.45);
  transform: translateY(-5px);
  box-shadow: 0 14px 30px rgba(22, 27, 34, 0.1);
}

.knowledge-card:hover::before {
  transform: scaleX(1);
}

@keyframes kbCardIn {
  from {
    opacity: 0;
    transform: translateY(18px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.card-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.pill {
  font-size: 12px;
  font-weight: 500;
  padding: 2px 10px;
  border-radius: 999px;
  transition:
    transform 0.25s cubic-bezier(0.22, 1, 0.36, 1),
    background 0.25s,
    color 0.25s,
    border-color 0.25s;
}

.pill-cat {
  background: #f6f8fa;
  color: #57606a;
  border: 1px solid #d8dee4;
}

.pill-easy {
  color: #1a7f37;
  background: rgba(26, 127, 55, 0.1);
  border: 1px solid rgba(26, 127, 55, 0.3);
}

.pill-mid {
  color: #9a6700;
  background: rgba(154, 103, 0, 0.08);
  border: 1px solid rgba(154, 103, 0, 0.3);
}

.pill-hard {
  color: #cf222e;
  background: rgba(207, 34, 46, 0.08);
  border: 1px solid rgba(207, 34, 46, 0.3);
}

.pill-none {
  color: #57606a;
  background: #f6f8fa;
  border: 1px solid #d8dee4;
}

.knowledge-card:hover .pill {
  transform: scale(1.06);
}

.knowledge-card:hover .pill-cat {
  background: rgba(46, 164, 79, 0.1);
  color: #2c974b;
  border-color: rgba(46, 164, 79, 0.3);
}

.card-more {
  margin-left: auto;
  width: 30px;
  height: 30px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #2ea44f;
  background: rgba(46, 164, 79, 0.1);
  opacity: 0;
  transform: scale(0.7) rotate(-90deg);
  transition:
    opacity 0.3s cubic-bezier(0.22, 1, 0.36, 1),
    transform 0.3s cubic-bezier(0.22, 1, 0.36, 1);
}

.card-more svg {
  width: 14px;
  height: 14px;
}

.knowledge-card:hover .card-more {
  opacity: 1;
  transform: scale(1) rotate(0deg);
}

.card-title {
  margin: 0 0 8px;
  font-size: 16px;
  font-weight: 600;
  color: #24292f;
  line-height: 1.45;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  transition: color 0.25s;
}

.knowledge-card:hover .card-title {
  color: #2c974b;
}

.card-summary {
  margin: 0 0 16px;
  font-size: 13px;
  color: #57606a;
  line-height: 1.65;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  flex: 1;
}

.card-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.card-kws {
  display: flex;
  gap: 5px;
  flex-wrap: wrap;
  min-width: 0;
}

.kw {
  font-size: 11px;
  color: #8c959f;
  background: #f6f8fa;
  border: 1px solid #e6e8eb;
  border-radius: 6px;
  padding: 1px 7px;
  transition: color 0.25s, border-color 0.25s, background 0.25s;
}

.knowledge-card:hover .kw {
  color: #2c974b;
  border-color: rgba(46, 164, 79, 0.25);
  background: rgba(46, 164, 79, 0.06);
}

.card-meta {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: #8c959f;
  font-variant-numeric: tabular-nums;
  flex-shrink: 0;
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 4px;
  transition: color 0.25s;
}

.meta-item svg {
  width: 13px;
  height: 13px;
  transition: transform 0.3s cubic-bezier(0.22, 1, 0.36, 1);
}

.knowledge-card:hover .meta-item {
  color: #2c974b;
}

.knowledge-card:hover .meta-item svg {
  transform: scale(1.15);
}
</style>
