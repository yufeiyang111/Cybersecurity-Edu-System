<template>
  <nav class="help-toc" aria-label="本文目录">
    <div class="help-toc__title">本页目录</div>
    <a
      v-for="(item, index) in visibleItems"
      :key="index"
      class="help-toc__item"
      :class="[
        `help-toc__item--level-${item.level}`,
        { 'is-active': item.id === activeId }
      ]"
      href="#"
      @click.prevent="scrollToHeading(item.id)"
    >
      {{ item.text }}
    </a>
  </nav>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  items: {
    type: Array,
    default: () => []
  },
  activeId: {
    type: String,
    default: ''
  }
})

const visibleItems = computed(() => props.items.filter((item) => item.level >= 2))

const scrollToHeading = (id) => {
  const el = document.getElementById(id)
  if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
}
</script>

<style scoped lang="scss">
.help-toc {
  position: sticky;
  top: 80px;
  flex-shrink: 0;
  width: 200px;
  max-height: calc(100vh - 100px);
  overflow-y: auto;
  padding: 4px 0 4px 16px;
  border-left: 1px solid var(--chat-hairline);

  &__title {
    font-size: 12px;
    font-weight: 600;
    color: var(--chat-hollow);
    margin-bottom: 10px;
    letter-spacing: 0.4px;
  }

  &__item {
    display: block;
    padding: 4px 8px;
    font-size: 13px;
    line-height: 1.5;
    color: var(--chat-muted);
    text-decoration: none;
    border-radius: var(--chat-radius);
    border-left: 2px solid transparent;
    margin-left: -16px;
    padding-left: 22px;
    transition: color 0.18s ease, border-color 0.18s ease, background 0.18s ease;

    &:hover {
      color: var(--chat-accent);
      background: var(--chat-hover);
    }

    &.is-active {
      color: var(--chat-accent);
      font-weight: 500;
      border-left-color: var(--chat-accent);
    }

    &--level-1 { font-weight: 500; }
    &--level-2 { padding-left: 34px; }
    &--level-3 { padding-left: 46px; color: var(--chat-hollow); }
    &--level-4 { padding-left: 58px; color: var(--chat-hollow); }
  }
}

@media (max-width: 1200px) {
  .help-toc {
    display: none;
  }
}
</style>