<template>
  <header class="llm-toolbar">
    <div>
      <h1>LLM 配置</h1>
      <p>管理多个 LLM 服务配置，自由切换不同模型提供商和 API 端点。</p>
    </div>
    <div class="llm-toolbar__actions">
      <BaseButton :disabled="loading" @click="$emit('test-all')">
        <BaseIcon name="refresh" :size="14" />
        测试连接
      </BaseButton>
      <BaseButton variant="primary" @click="$emit('create')">
        <BaseIcon name="plus" :size="14" />
        添加 LLM 配置
      </BaseButton>
    </div>
  </header>
</template>

<script setup>
import { BaseButton, BaseIcon } from '@/components/ui'

defineProps({ loading: { type: Boolean, default: false } })
defineEmits(['create', 'test-all'])
</script>

<style scoped lang="scss">
.llm-toolbar { display: flex; align-items: flex-start; justify-content: space-between; gap: 20px; margin-bottom: 22px; }
.llm-toolbar h1 { margin: 0; color: #0f172a; font-size: 20px; line-height: 1.35; }
.llm-toolbar p { margin: 5px 0 0; color: #475569; font-size: 13px; }
.llm-toolbar__actions { display: flex; gap: 8px; flex-shrink: 0; }
@media (max-width: 640px) { .llm-toolbar { flex-direction: column; } .llm-toolbar__actions { width: 100%; justify-content: flex-end; } }
</style>
