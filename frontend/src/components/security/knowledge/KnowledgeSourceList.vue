<template>
  <article class="panel sources-panel">
    <div class="panel-heading">
      <div>
        <h2>知识来源</h2>
        <p>仅工作区 Owner 或安全管理员可维护。</p>
      </div>
      <span class="count-badge">{{ sources.length }}</span>
    </div>

    <el-empty v-if="!loading && sources.length === 0" description="还没有安全知识源。" />
    <div v-else class="source-list">
      <button
        v-for="source in sources"
        :key="source.id"
        type="button"
        class="source-card"
        :class="{ selected: selectedSource?.id === source.id }"
        @click="emit('select-source', source)"
      >
        <div class="source-card__top">
          <strong>{{ source.name }}</strong>
          <el-tag size="small" :type="source.is_active ? 'success' : 'info'">{{ source.is_active ? '生效中' : '已停用' }}</el-tag>
        </div>
        <span>{{ source.source_type }} · {{ source.source_version }}</span>
        <small>{{ source.license_name || '未声明许可证' }}</small>
      </button>
    </div>
  </article>
</template>

<script setup>
defineProps({
  sources: { type: Array, default: () => [] },
  selectedSource: { type: Object, default: null },
  loading: { type: Boolean, default: false }
})

const emit = defineEmits(['select-source'])
</script>

<style scoped lang="scss">
.panel { background:#fff; border:1px solid #e6eaf0; border-radius:16px; padding:24px; box-shadow:0 10px 30px rgba(20,33,61,.06); }
.panel-heading { display:flex; gap:16px; align-items:flex-start; justify-content:space-between; margin-bottom:20px; }
.panel-heading h2 { margin:0; font-size:19px; }
.panel-heading p { margin:7px 0 0; color:#788496; line-height:1.55; }
.count-badge { display:grid; place-items:center; min-width:32px; height:32px; border-radius:16px; background:#edf8f4; color:#167359; font-weight:700; }
.source-list { display:grid; gap:10px; }
.source-card { width:100%; text-align:left; border:1px solid #e6eaf0; border-radius:10px; padding:14px; color:inherit; background:#fff; cursor:pointer; transition:.15s ease; }
.source-card:hover,.source-card.selected { border-color:#36a883; background:#f3fcf8; }
.source-card__top { display:flex; align-items:center; justify-content:space-between; gap:8px; }
.source-card span,.source-card small { display:block; margin-top:8px; color:#718096; }
.source-card small { font-size:12px; }
@media(max-width:820px){ .panel{padding:18px} }
</style>
