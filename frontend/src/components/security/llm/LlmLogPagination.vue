<template>
  <footer class="pagination-bar">
    <span>总计：{{ pagination.total }} 条</span>
    <div class="pagination-bar__right">
      <label class="per-page">
        每页行数
        <select :value="pagination.perPage" @change="$emit('change-per-page', $event.target.value)">
          <option value="10">10</option>
          <option value="20">20</option>
          <option value="50">50</option>
          <option value="100">100</option>
        </select>
      </label>
      <div class="pages">
        <button :disabled="pagination.page <= 1" @click="$emit('change-page', pagination.page - 1)">
          ‹
        </button>
        <button
          v-for="page in visiblePages"
          :key="page"
          :class="{ active: page === pagination.page }"
          @click="$emit('change-page', page)"
        >
          {{ page }}
        </button>
        <button :disabled="pagination.page >= pagination.pages" @click="$emit('change-page', pagination.page + 1)">
          ›
        </button>
      </div>
    </div>
  </footer>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  pagination: { type: Object, required: true }
})

defineEmits(['change-page', 'change-per-page'])

const visiblePages = computed(() => {
  const total = Math.max(props.pagination.pages || 1, 1)
  const current = Math.min(props.pagination.page, total)
  const half = 2
  let start = Math.max(1, current - half)
  const end = Math.min(total, start + half * 2)
  start = Math.max(1, end - half * 2)
  const pages = []
  for (let page = start; page <= end; page += 1) {
    pages.push(page)
  }
  return pages
})
</script>

<style scoped lang="scss">
.pagination-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-height: 60px;
  padding: 8px 12px;
  color: #475569;
  font-size: 12px;
}

.pagination-bar__right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.per-page {
  display: flex;
  align-items: center;
  gap: 6px;
}

.per-page select {
  height: 30px;
  margin-left: 6px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  background: #fff;
  color: #475569;
}

.pages {
  display: flex;
  align-items: center;
  gap: 6px;
}

.pages button {
  width: 30px;
  height: 30px;
  padding: 0;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  background: #fff;
  color: #475569;
  cursor: pointer;
}

.pages button.active {
  border-color: #2563eb;
  background: #2563eb;
  color: #fff;
}

.pages button:disabled {
  color: #cbd5e1;
  cursor: not-allowed;
}

@media (max-width: 640px) {
  .pagination-bar {
    align-items: flex-start;
    flex-direction: column;
  }

  .pagination-bar__right {
    width: 100%;
    justify-content: space-between;
  }
}
</style>
