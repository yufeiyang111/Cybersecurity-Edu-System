<template>
  <section class="chain-card">
    <div class="card-head">
      <h2>引用链</h2>
    </div>
    <div class="chain-search">
      <el-input
        v-model="symbol"
        size="small"
        placeholder="输入符号名，查询引用方"
        @keyup.enter="search"
      />
      <el-button size="small" :loading="loading" @click="search">查询</el-button>
    </div>
    <div v-if="loading" class="chain-card__empty">查询中…</div>
    <template v-else-if="chains.length">
      <div v-for="(chain, index) in chains" :key="index" class="chain-step">
        <span class="chain-step__badge">{{ chain.typeLabel }}</span>
        <span class="chain-step__label">{{ chain.label }}</span>
        <span class="chain-step__file">{{ chain.filePath }}</span>
      </div>
      <p v-if="truncated" class="chain-card__hint">已达深度上限，仅显示前 {{ chains.length }} 层</p>
    </template>
    <p v-else-if="queried" class="chain-card__empty">未找到该符号的引用链</p>
    <p v-else class="chain-card__hint">点击图中节点或输入符号，查看其上游引用</p>
  </section>
</template>

<script setup>
import { ref } from 'vue'
import { agentAPI } from '@/api'
import { useProjectSecurityGraph } from '@/composables/security/useProjectSecurityGraph'

const props = defineProps({
  runId: { type: Number, default: null }
})

const symbol = ref('')
const chains = ref([])
const loading = ref(false)
const queried = ref(false)
const truncated = ref(false)
const { nodeMeta } = useProjectSecurityGraph(() => props.runId)

async function search() {
  const query = (symbol.value || '').trim()
  if (!query || !props.runId) return
  loading.value = true
  queried.value = true
  truncated.value = false
  try {
    const neighbors = []
    const runId = props.runId
    let offset = 0
    while (offset < 100) {
      const response = await agentAPI.getGraph(runId, { limit: 50, offset })
      offset += 50
      neighbors.push(...(response.entry_nodes || []))
      if ((response.pagination?.total || 0) <= offset) break
    }
    const matches = neighbors.filter((node) => node.label === query)
    if (matches.length === 0) {
      chains.value = []
      return
    }
    const visited = new Set()
    const result = []
    const frontier = matches.slice(0, 5)
    for (let depth = 0; depth < 4 && frontier.length; depth += 1) {
      const current = frontier.shift()
      if (visited.has(current.id)) continue
      visited.add(current.id)
      result.push(current)
      const nodeResponse = await agentAPI.getGraphNeighbors(runId, current.id, { limit: 20, offset: 0 })
      const incoming = (nodeResponse.edges || []).filter((edge) => edge.target_node_id === current.id)
      for (const edge of incoming) {
        const sourceId = edge.source_node_id
        if (visited.has(sourceId)) continue
        const source = edge.source_node
        if (source) frontier.push({ ...source, nodeType: source.node_type })
      }
    }
    chains.value = result.map((node) => ({
      id: node.id,
      label: node.label,
      nodeType: node.node_type,
      typeLabel: nodeMeta(node.node_type).label,
      filePath: node.file_path
    }))
    truncated.value = result.length >= 20
  } catch (error) {
    chains.value = []
  } finally {
    loading.value = false
  }
}
</script>

<style scoped lang="scss">
.chain-card {
  background: #fff;
  border: 1px solid #e2e7ee;
  border-radius: 8px;
  padding: 14px 16px;
}
.card-head { margin-bottom: 8px; }
.card-head h2 { margin: 0; font-size: 15px; font-weight: 600; }
.chain-search {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 10px;
}
.chain-step {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12.5px;
  padding: 5px 0;
  border-bottom: 1px dashed #eef1f5;
}
.chain-step__badge {
  flex: none;
  font-size: 11px;
  color: #2563eb;
  background: #eff6ff;
  border-radius: 4px;
  padding: 1px 6px;
}
.chain-step__label {
  color: #1f2d3d;
  font-weight: 600;
  word-break: break-all;
}
.chain-step__file {
  color: #94a3b8;
  font-size: 11.5px;
  word-break: break-all;
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.chain-card__empty { color: #8494a8; font-size: 12.5px; padding: 4px 0; }
.chain-card__hint { color: #94a3b8; font-size: 12px; margin: 4px 0 0; }
</style>
