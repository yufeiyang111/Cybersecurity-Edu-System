<template>
  <aside class="help-sidebar">
    <div v-if="loading" class="help-sidebar__loading">
      <div class="skeleton-block w-50"></div>
      <div class="skeleton-block w-90"></div>
      <div class="skeleton-block w-75"></div>
      <div class="skeleton-block w-60"></div>
      <div class="skeleton-block w-85"></div>
    </div>
    <nav v-else class="help-sidebar__nav">
      <template v-for="(category, catIndex) in tree" :key="category.id">
        <div
          v-if="hasDocuments(category)"
          class="help-group"
          :style="{ animationDelay: `${catIndex * 70}ms` }"
        >
          <div class="help-group__title">{{ category.name }}</div>
          <template v-for="child in category.children" :key="child.id">
            <div v-if="child.documents && child.documents.length" class="help-group__sub">
              <div class="help-group__subtitle">{{ child.name }}</div>
              <button
                v-for="doc in child.documents"
                :key="doc.id"
                type="button"
                class="help-group__doc"
                :class="{ 'is-active': doc.slug === activeSlug }"
                @click="$emit('select-document', doc.slug)"
              >
                {{ doc.title }}
              </button>
            </div>
          </template>
          <template v-if="!category.children || !category.children.length">
            <button
              v-for="doc in category.documents"
              :key="doc.id"
              type="button"
              class="help-group__doc"
              :class="{ 'is-active': doc.slug === activeSlug }"
              @click="$emit('select-document', doc.slug)"
            >
              {{ doc.title }}
            </button>
          </template>
        </div>
      </template>
    </nav>
  </aside>
</template>

<script setup>
defineProps({
  tree: {
    type: Array,
    default: () => []
  },
  activeSlug: {
    type: String,
    default: ''
  },
  loading: {
    type: Boolean,
    default: false
  }
})

defineEmits(['select-document'])

const hasDocuments = (category) => {
  if (category.documents && category.documents.length) return true
  if (!category.children || !category.children.length) return false
  return category.children.some((child) => child.documents && child.documents.length)
}
</script>

<style scoped lang="scss">
.help-sidebar {
  position: sticky;
  top: 56px;
  width: 280px;
  flex-shrink: 0;
  border-right: 1px solid var(--chat-hairline);
  background: var(--chat-sidebar);
  height: calc(100vh - 56px);
  overflow-y: auto;
  padding: 24px 12px 40px;

  &__loading {
    .skeleton-block {
      height: 14px;
      border-radius: 4px;
      background: var(--chat-hover);
      margin-bottom: 14px;

      &.w-50 { width: 50%; }
      &.w-60 { width: 60%; }
      &.w-75 { width: 75%; }
      &.w-85 { width: 85%; }
      &.w-90 { width: 90%; }
    }
  }

  &__nav {
    display: flex;
    flex-direction: column;
    gap: 24px;
  }
}

.help-group {
  animation: group-fade-in 0.35s ease both;

  @keyframes group-fade-in {
    from {
      opacity: 0;
      transform: translateX(-8px);
    }
    to {
      opacity: 1;
      transform: translateX(0);
    }
  }

  &__title {
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.4px;
    color: var(--chat-hollow);
    padding: 0 12px 8px;
    text-transform: uppercase;
  }

  &__sub {
    margin-bottom: 4px;

    &title {
      font-size: 12px;
      color: var(--chat-hollow);
      padding: 6px 12px 4px;
    }
  }

  &__doc {
    display: flex;
    align-items: center;
    width: 100%;
    padding: 8px 12px;
    border: none;
    background: none;
    border-radius: var(--chat-radius);
    font-size: 14px;
    line-height: 1.5;
    color: var(--chat-muted);
    cursor: pointer;
    text-align: left;
    position: relative;
    transition: background 0.16s ease, color 0.16s ease, transform 0.16s ease;

    &:hover {
      background: var(--chat-hover);
      color: var(--chat-ink);
      transform: translateX(2px);
    }

    &.is-active {
      background: var(--chat-accent-soft);
      color: var(--chat-accent);
      font-weight: 500;

      &::before {
        content: '';
        position: absolute;
        left: 0;
        top: 8px;
        bottom: 8px;
        width: 3px;
        border-radius: 0 3px 3px 0;
        background: var(--chat-accent);
      }
    }
  }
}

@media (prefers-reduced-motion: reduce) {
  .help-group {
    animation: none;
  }
}

@media (max-width: 1024px) {
  .help-sidebar {
    width: 240px;
  }
}

@media (max-width: 768px) {
  .help-sidebar {
    position: fixed;
    z-index: 90;
    left: 0;
    top: 56px;
    bottom: 0;
    width: 280px;
    transform: translateX(-100%);
    transition: transform 0.2s ease;
    box-shadow: 0 4px 24px rgba(0, 0, 0, 0.12);
  }
}
</style>