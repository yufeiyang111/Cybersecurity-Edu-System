<template>
  <div class="filters-shell">
    <div class="filter-tabs" role="tablist" aria-label="项目筛选">
      <button
        v-for="item in filterItems"
        :key="item.key"
        type="button"
        class="filter-tab"
        :class="{ active: filter === item.key }"
        @click="$emit('update:filter', item.key)"
      >
        {{ item.label }}
        <b>{{ item.count }}</b>
      </button>
    </div>

    <div class="filter-actions">
      <label class="search-box">
        <BaseIcon name="search" :size="15" />
        <input
          :value="search"
          type="search"
          placeholder="搜索项目"
          aria-label="搜索项目"
          @input="$emit('update:search', $event.target.value)"
        />
      </label>
      <select
        :value="language"
        aria-label="按语言筛选"
        @change="$emit('update:language', $event.target.value)"
      >
        <option value="all">全部语言</option>
        <option value="python">Python</option>
        <option value="javascript">JavaScript / TypeScript</option>
        <option value="java">Java</option>
        <option value="go">Go</option>
        <option value="unknown">未知</option>
      </select>
      <select
        :value="sort"
        aria-label="项目排序"
        @change="$emit('update:sort', $event.target.value)"
      >
        <option value="recent">最近活动</option>
        <option value="name">项目名称</option>
        <option value="risk">风险数量</option>
      </select>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { BaseIcon } from '@/components/ui'

const props = defineProps({
  filter: { type: String, default: 'all' },
  search: { type: String, default: '' },
  language: { type: String, default: 'all' },
  sort: { type: String, default: 'recent' },
  projects: { type: Array, default: () => [] }
})

defineEmits(['update:filter', 'update:search', 'update:language', 'update:sort'])

const filterItems = computed(() => [
  { key: 'all', label: '全部', count: props.projects.length },
  { key: 'running', label: '正在运行', count: props.projects.filter((project) => project.is_running).length },
  { key: 'attention', label: '有风险', count: props.projects.filter((project) => riskTotal(project) > 0).length },
  { key: 'unscanned', label: '未审计', count: props.projects.filter((project) => !project.last_scan_at).length }
])

function riskTotal(project) {
  return Object.values(project.vulns || {}).reduce((total, value) => total + (Number(value) || 0), 0)
}
</script>

<style scoped lang="scss">
.filters-shell {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin: 16px 0 12px;
  padding: 6px 0;
}

.filter-tabs,
.filter-actions {
  display: flex;
  align-items: center;
  gap: 6px;
}

.filter-tab {
  height: 31px;
  padding: 0 12px;
  border: 1px solid transparent;
  border-radius: 6px;
  color: #64748b;
  background: transparent;
  font-size: 13px;
  transition: transform 0.2s ease, color 0.2s ease, background 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
}

.filter-tab:hover {
  color: #2563eb;
  background: #f8fafc;
  transform: translateY(-1px);
}

.filter-tab:active {
  transform: translateY(0);
}

.filter-tab.active {
  border-color: #dbeafe;
  color: #2563eb;
  background: #eff6ff;
  font-weight: 600;
  box-shadow: 0 2px 6px rgba(37, 99, 235, 0.12);
}

.filter-tab b {
  margin-left: 3px;
  color: #94a3b8;
  font-size: 11px;
  font-weight: 500;
}

.filter-tab.active b {
  color: #2563eb;
}

.search-box {
  width: 225px;
  height: 34px;
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 0 11px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  background: #fff;
  transition: border-color 0.18s ease, box-shadow 0.18s ease, transform 0.2s ease;
}

.search-box:hover {
  border-color: #c7d5f7;
  transform: translateY(-1px);
}

.search-box:focus-within {
  border-color: #93b4f7;
  box-shadow: 0 0 0 3px #eff6ff;
}

.search-box :deep(.ui-icon) {
  color: #94a3b8;
}

.search-box input {
  width: 100%;
  min-width: 0;
  border: 0;
  outline: 0;
  color: #172033;
  background: transparent;
  font-size: 13px;
}

.search-box input::placeholder {
  color: #94a3b8;
}

select {
  height: 34px;
  max-width: 150px;
  padding: 0 28px 0 11px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  color: #40506a;
  background: #fff;
  font-size: 13px;
  outline: 0;
  cursor: pointer;
  transition: border-color 0.18s ease, box-shadow 0.18s ease, transform 0.2s ease;
}

select:hover {
  border-color: #c7d5f7;
  transform: translateY(-1px);
}

select:focus {
  border-color: #93b4f7;
  box-shadow: 0 0 0 3px #eff6ff;
}

@media (prefers-reduced-motion: reduce) {
  .filter-tab,
  .search-box,
  select {
    transition: none;
    transform: none;
  }
  .filter-tab:hover,
  .search-box:hover,
  select:hover {
    transform: none;
  }
}

@media (max-width: 860px) {
  .filters-shell {
    align-items: stretch;
    flex-direction: column;
  }
  .filter-tabs {
    overflow-x: auto;
  }
  .filter-tab {
    flex: 0 0 auto;
  }
  .filter-actions {
    width: 100%;
  }
  .search-box {
    flex: 1;
    width: auto;
  }
  select {
    flex: 0 0 auto;
  }
}
</style>
