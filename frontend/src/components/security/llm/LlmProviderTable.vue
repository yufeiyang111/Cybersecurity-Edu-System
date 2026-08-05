<template>
  <div class="provider-table-wrap">
    <div v-if="!loading && providers.length === 0" class="empty-state">
      <BaseIcon name="server" :size="30" />
      <strong>还没有 LLM 配置</strong>
      <span>添加一个 OpenAI 兼容服务后即可开始使用。</span>
      <BaseButton variant="primary" @click="$emit('create')">添加 LLM 配置</BaseButton>
    </div>
    <div v-else class="table-scroll">
      <table class="provider-table">
        <thead><tr><th class="check-col"><input type="checkbox" aria-label="全选" /></th><th>名称</th><th>状态</th><th>API 地址</th><th>额度</th><th>分组</th><th>模型 / 价格倍率</th><th>IP 限制</th><th>创建时间</th><th>操作</th></tr></thead>
        <tbody v-if="loading"><tr v-for="index in 3" :key="index" class="skeleton-row"><td colspan="10"><span /></td></tr></tbody>
        <tbody v-else>
          <tr v-for="provider in providers" :key="provider.id">
            <td class="check-col"><input type="checkbox" :aria-label="`选择 ${provider.name}`" /></td>
            <td><strong>{{ provider.name }}</strong></td>
            <td><LlmProviderStatusBadge :provider="provider" /></td>
            <td><span class="ellipsis" :title="provider.base_url">{{ provider.base_url }}</span></td>
            <td><strong>无限制</strong></td>
            <td><BaseBadge type="blue">OpenAI 兼容</BaseBadge></td>
            <td><span class="model-cell">{{ provider.model }}</span></td>
            <td><span class="muted">未配置</span></td>
            <td>{{ relativeTime(provider.created_at) }}</td>
            <td><div class="row-actions"><button class="icon-action" :class="{ spinning: testing === provider.id }" :disabled="testing === provider.id" title="测试连接" @click="$emit('test', provider)"><BaseIcon name="refresh" :size="15" :class="{ 'icon-spinning': testing === provider.id }" /></button><button class="icon-action" title="编辑" @click="$emit('edit', provider)"><BaseIcon name="pencil" :size="15" /></button><button class="icon-action danger" title="删除" @click="$emit('delete', provider)"><BaseIcon name="trash" :size="15" /></button></div></td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { BaseBadge, BaseButton, BaseIcon } from '@/components/ui'
import LlmProviderStatusBadge from './LlmProviderStatusBadge.vue'
import { formatRelativeTime } from '@/features/security/llm/format'

defineProps({ providers: { type: Array, default: () => [] }, loading: { type: Boolean, default: false }, testing: { type: Number, default: null } })
defineEmits(['create', 'test', 'edit', 'delete'])
const relativeTime = formatRelativeTime
</script>

<style scoped lang="scss">
.provider-table-wrap { min-height: 360px; }
.table-scroll { overflow-x: auto; }
table { width: 100%; min-width: 1080px; border-collapse: collapse; table-layout: fixed; }
th, td { padding: 12px 10px; border-bottom: 1px solid #e2e8f0; text-align: left; vertical-align: middle; }
th { height: 44px; color: #94a3b8; background: #f1f5f9; font-size: 12px; font-weight: 600; }
td { height: 66px; color: #475569; font-size: 13px; }
tbody tr:hover { background: #f8fafc; }
tr:last-child td { border-bottom: 0; }
th:nth-child(2), td:nth-child(2) { width: 11%; } th:nth-child(3), td:nth-child(3) { width: 11%; } th:nth-child(4), td:nth-child(4) { width: 18%; } th:nth-child(5), td:nth-child(5) { width: 9%; } th:nth-child(6), td:nth-child(6) { width: 16%; } th:nth-child(7), td:nth-child(7) { width: 13%; } th:nth-child(8), td:nth-child(8) { width: 9%; } th:nth-child(9), td:nth-child(9) { width: 10%; } th:nth-child(10), td:nth-child(10) { width: 110px; }
.check-col { width: 42px; } input[type='checkbox'] { width: 17px; height: 17px; accent-color: #2563eb; }
.muted { color: #94a3b8; }
.icon-action { width: 27px; height: 27px; display: inline-flex; align-items: center; justify-content: center; padding: 0; border: 0; border-radius: 4px; background: transparent; color: #475569; }
.icon-action:hover { background: #eff6ff; color: #2563eb; } .icon-action.danger:hover { background: #fef2f2; color: #dc2626; } .icon-action:disabled { opacity: 0.5; cursor: not-allowed; } .icon-spinning { animation: spin 0.8s linear infinite; } @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
.row-actions { display: flex; gap: 3px; } .ellipsis { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #475569; } .model-cell { color: #0f172a; font-weight: 600; }
.skeleton-row td { height: 66px; } .skeleton-row span { display: block; width: 100%; height: 14px; border-radius: 4px; background: #f1f5f9; animation: skeleton 1.4s ease-in-out infinite alternate; }
@keyframes skeleton { from { opacity: .55; } to { opacity: 1; } }
.empty-state { min-height: 360px; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 10px; color: #94a3b8; } .empty-state strong { color: #0f172a; } .empty-state span { font-size: 13px; }
</style>
