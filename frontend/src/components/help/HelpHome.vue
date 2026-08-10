<template>
  <div class="help-home">
    <div class="help-home__hero">
      <h1 class="help-home__title">需要帮助？</h1>
      <p class="help-home__desc">从下面的指南开始，或选择左侧目录中的文档。</p>
    </div>

    <div v-if="loading" class="help-home__grid">
      <div v-for="i in 4" :key="i" class="help-home__card-skeleton"></div>
    </div>

    <div v-else class="help-home__grid">
      <section
        v-for="(category, index) in tree"
        :key="category.id"
        class="help-card"
        :style="{ animationDelay: `${120 + index * 80}ms` }"
      >
        <h2 class="help-card__title">{{ category.name }}</h2>
        <p v-if="category.description" class="help-card__desc">{{ category.description }}</p>
        <ul class="help-card__list">
          <template v-for="child in category.children" :key="child.id">
            <li v-for="doc in child.documents" :key="doc.id">
              <button
                type="button"
                class="help-card__link"
                @click="$emit('select-document', doc.slug)"
              >
                <span class="help-card__link-text">{{ doc.title }}</span>
                <BaseIcon name="arrow-right" :size="14" class="help-card__link-icon" />
              </button>
            </li>
          </template>
          <template v-if="!category.children || !category.children.length">
            <li v-for="doc in category.documents" :key="doc.id">
              <button
                type="button"
                class="help-card__link"
                @click="$emit('select-document', doc.slug)"
              >
                <span class="help-card__link-text">{{ doc.title }}</span>
                <BaseIcon name="arrow-right" :size="14" class="help-card__link-icon" />
              </button>
            </li>
          </template>
        </ul>
      </section>
    </div>
  </div>
</template>

<script setup>
import { BaseIcon } from '@/components/ui'

defineProps({
  tree: {
    type: Array,
    default: () => []
  },
  loading: {
    type: Boolean,
    default: false
  }
})

defineEmits(['select-document'])
</script>

<style scoped lang="scss">
.help-home {
  max-width: 860px;

  &__hero {
    padding: 24px 0 36px;
    animation: hero-fade-up 0.45s ease both;
  }

  &__title {
    margin: 0 0 10px;
    font-size: 32px;
    font-weight: 700;
    color: var(--chat-ink);
    letter-spacing: -0.01em;
  }

  &__desc {
    margin: 0;
    font-size: 15px;
    color: var(--chat-muted);
  }

  &__grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 16px;
  }

  &__card-skeleton {
    height: 180px;
    border-radius: var(--chat-radius);
    border: 1px solid var(--chat-hairline);
    background: linear-gradient(90deg, var(--chat-hover) 25%, var(--chat-hairline) 50%, var(--chat-hover) 75%);
    background-size: 200% 100%;
    animation: shimmer 1.2s infinite;
  }
}

@keyframes hero-fade-up {
  from {
    opacity: 0;
    transform: translateY(12px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

.help-card {
  border: 1px solid var(--chat-hairline-strong);
  border-radius: var(--chat-radius);
  padding: 20px 22px;
  background: var(--chat-field);
  animation: hero-fade-up 0.45s ease both;
  transition: box-shadow 0.2s ease, border-color 0.2s ease, transform 0.2s ease;

  &:hover {
    border-color: var(--chat-accent-border);
    box-shadow: 0 6px 20px rgba(0, 0, 0, 0.08);
    transform: translateY(-2px);
  }

  &__title {
    margin: 0 0 6px;
    font-size: 16px;
    font-weight: 600;
    color: var(--chat-ink);
  }

  &__desc {
    margin: 0 0 14px;
    font-size: 13px;
    line-height: 1.6;
    color: var(--chat-hollow);
  }

  &__list {
    list-style: none;
    margin: 0;
    padding: 0;
  }

  &__link {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    width: 100%;
    padding: 8px 6px;
    border: none;
    background: none;
    border-radius: var(--chat-radius);
    cursor: pointer;
    text-align: left;
    transition: background 0.16s ease;

    &:hover {
      background: var(--chat-hover);

      .help-card__link-text {
        color: var(--chat-accent);
      }

      .help-card__link-icon {
        color: var(--chat-accent);
        transform: translateX(3px);
      }
    }
  }

  &__link-text {
    font-size: 14px;
    color: var(--chat-muted);
    line-height: 1.5;
    transition: color 0.16s ease;
  }

  &__link-icon {
    flex-shrink: 0;
    color: var(--chat-hollow);
    transition: transform 0.18s ease, color 0.16s ease;
  }
}

@media (prefers-reduced-motion: reduce) {
  .help-home__hero,
  .help-card {
    animation: none;
  }
}

@media (max-width: 768px) {
  .help-home {
    &__title {
      font-size: 26px;
    }

    &__grid {
      grid-template-columns: 1fr;
    }
  }
}
</style>