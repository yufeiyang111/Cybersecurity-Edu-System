<template>
  <aside class="kb-sidebar">
    <header class="sidebar-head">
      <span class="head-dot"></span>
      <span class="head-title">知识分类</span>
    </header>
    <nav class="category-list">
      <button
        type="button"
        class="category-item"
        :class="{ active: active === '' }"
        @click="$emit('select', '')"
      >
        <span class="item-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <path d="M14 2v6h6" />
          </svg>
        </span>
        <span class="item-name">全部知识</span>
        <span class="item-count">{{ allCount }}</span>
      </button>
      <button
        v-for="cat in categories"
        :key="cat.id"
        type="button"
        class="category-item"
        :class="{ active: active === String(cat.id) }"
        @click="$emit('select', String(cat.id))"
      >
        <span class="item-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
          </svg>
        </span>
        <span class="item-name">{{ cat.name }}</span>
        <span class="item-count">{{ cat.item_count }}</span>
      </button>
    </nav>
  </aside>
</template>

<script setup>
defineProps({
  categories: {
    type: Array,
    default: () => []
  },
  active: {
    type: String,
    default: ''
  },
  allCount: {
    type: Number,
    default: 0
  }
})

defineEmits(['select'])
</script>

<style lang="scss" scoped>
.kb-sidebar {
  width: 240px;
  flex-shrink: 0;
  background: #fff;
  border: 1px solid #d8dee4;
  border-radius: 12px;
  align-self: flex-start;
  position: sticky;
  top: 20px;
  overflow: hidden;
  transition: box-shadow 0.3s;
}

.kb-sidebar:hover {
  box-shadow: 0 8px 24px rgba(22, 27, 34, 0.06);
}

.sidebar-head {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 14px 16px;
  border-bottom: 1px solid #e6e8eb;
}

.head-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #2ea44f;
  animation: kbPing 2.2s ease-out infinite;
}

@keyframes kbPing {
  0% {
    box-shadow: 0 0 0 0 rgba(46, 164, 79, 0.5);
  }
  70%,
  100% {
    box-shadow: 0 0 0 7px rgba(46, 164, 79, 0);
  }
}

.head-title {
  font-size: 14px;
  font-weight: 600;
  color: #24292f;
}

.category-list {
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.category-item {
  position: relative;
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 9px 10px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: #57606a;
  font-size: 13.5px;
  font-family: inherit;
  cursor: pointer;
  text-align: left;
  transition:
    background 0.2s,
    color 0.2s,
    transform 0.2s;
}

.category-item::before {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  width: 3px;
  height: 60%;
  border-radius: 3px;
  background: #2ea44f;
  transform: translateY(-50%) scaleY(0);
  transform-origin: center;
  transition: transform 0.3s cubic-bezier(0.22, 1, 0.36, 1);
}

.category-item:hover {
  background: #f6f8fa;
  color: #2c974b;
}

.category-item:hover .item-icon {
  color: #2ea44f;
  border-color: rgba(46, 164, 79, 0.35);
  background: rgba(46, 164, 79, 0.08);
}

.category-item.active {
  background: rgba(46, 164, 79, 0.1);
  color: #2c974b;
  font-weight: 600;
}

.category-item.active::before {
  transform: translateY(-50%) scaleY(1);
}

.category-item.active .item-icon {
  color: #2ea44f;
  border-color: rgba(46, 164, 79, 0.35);
  background: rgba(46, 164, 79, 0.12);
}

.item-icon {
  width: 26px;
  height: 26px;
  border-radius: 7px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #8c959f;
  background: #f6f8fa;
  border: 1px solid #e6e8eb;
  flex-shrink: 0;
  transition:
    color 0.2s,
    border-color 0.2s,
    background 0.2s,
    transform 0.25s cubic-bezier(0.22, 1, 0.36, 1);
}

.category-item:hover .item-icon {
  transform: scale(1.08);
}

.item-icon svg {
  width: 13px;
  height: 13px;
}

.item-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.item-count {
  font-size: 11px;
  color: #8c959f;
  background: #f6f8fa;
  border: 1px solid #e6e8eb;
  border-radius: 999px;
  padding: 0 7px;
  line-height: 17px;
  font-variant-numeric: tabular-nums;
  transition:
    background 0.2s,
    color 0.2s,
    border-color 0.2s;
}

.category-item:hover .item-count {
  color: #2c974b;
  border-color: rgba(46, 164, 79, 0.3);
  background: rgba(46, 164, 79, 0.06);
}

.category-item.active .item-count {
  color: #2c974b;
  border-color: rgba(46, 164, 79, 0.3);
  background: #fff;
}

/* ==================== 响应式 ==================== */
@media (max-width: 768px) {
  .kb-sidebar {
    width: 100%;
    position: static;
  }

  .sidebar-head {
    display: none;
  }

  .category-list {
    flex-direction: row;
    overflow-x: auto;
    gap: 8px;
    padding: 10px 12px;
  }

  .category-item {
    flex: 0 0 auto;
    width: auto;
    padding: 8px 14px;
    border-radius: 999px;
    border: 1px solid #d8dee4;
    white-space: nowrap;
  }

  .category-item::before {
    display: none;
  }

  .item-icon {
    display: none;
  }
}
</style>
