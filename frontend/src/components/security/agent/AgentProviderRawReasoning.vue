<template>
  <BasePanel
    v-if="eligible"
    class="provider-raw-reasoning"
  >
    <template #header>
      <div class="provider-raw-reasoning__header">
        <div class="provider-raw-reasoning__heading">
          <div class="provider-raw-reasoning__title-row">
            <BaseIcon
              name="eye"
              :size="16"
            />
            <h3>Provider 原始推理输出</h3>
          </div>
          <p>仅展示 Provider 明确返回的 reasoning；不属于经验证的漏洞证据。</p>
        </div>
        <BaseBadge
          :type="live ? 'green' : 'gray'"
          :dot="live"
          :pulse="live"
        >
          {{ live ? '实时' : terminal ? '已结束' : '等待输出' }}
        </BaseBadge>
      </div>
    </template>

    <div class="provider-raw-reasoning__body">
      <p class="provider-raw-reasoning__notice">
        仅任务发起人的当前活动连接可见；刷新、重连或进入历史任务后均无法回放。
      </p>
      <BaseButton
        class="provider-raw-reasoning__toggle"
        variant="ghost"
        type="button"
        :aria-expanded="expanded"
        @click="expanded = !expanded"
      >
        <BaseIcon
          :name="expanded ? 'chevron-down' : 'eye'"
          :size="15"
        />
        {{ expanded ? '收起原始输出' : '展开原始输出' }}
      </BaseButton>

      <div
        v-if="expanded"
        class="provider-raw-reasoning__content"
      >
        <pre v-if="text">{{ text }}</pre>
        <p
          v-else
          class="provider-raw-reasoning__empty"
        >
          {{ terminal ? '本次 Provider 未返回可展示的 reasoning。' : '等待 Provider 返回 reasoning delta…' }}
        </p>
      </div>
    </div>
  </BasePanel>
</template>

<script setup>
import { ref } from 'vue'
import {
  BaseBadge,
  BaseButton,
  BaseIcon,
  BasePanel,
} from '@/components/ui'

defineProps({
  eligible: { type: Boolean, default: false },
  text: { type: String, default: '' },
  live: { type: Boolean, default: false },
  terminal: { type: Boolean, default: false },
})

const expanded = ref(false)
</script>

<style scoped lang="scss">
.provider-raw-reasoning {
  border-color: #dbe4ee;
}

.provider-raw-reasoning__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  width: 100%;
}

.provider-raw-reasoning__heading {
  min-width: 0;
}

.provider-raw-reasoning__title-row {
  display: flex;
  align-items: center;
  gap: 7px;
  color: #334155;
}

.provider-raw-reasoning__title-row h3 {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
}

.provider-raw-reasoning__heading p {
  margin: 4px 0 0;
  color: #64748b;
  font-size: 12px;
  line-height: 1.5;
}

.provider-raw-reasoning__body {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.provider-raw-reasoning__notice {
  margin: 0;
  color: #64748b;
  font-size: 12px;
  line-height: 1.6;
}

.provider-raw-reasoning__toggle {
  align-self: flex-start;
}

.provider-raw-reasoning__content {
  max-height: 280px;
  overflow: auto;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  background: #f8fafc;
}

.provider-raw-reasoning__content pre {
  margin: 0;
  padding: 11px 12px;
  color: #334155;
  font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
  font-size: 12px;
  line-height: 1.65;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.provider-raw-reasoning__empty {
  margin: 0;
  padding: 12px;
  color: #94a3b8;
  font-size: 12px;
  line-height: 1.6;
}

@media (max-width: 768px) {
  .provider-raw-reasoning__content {
    max-height: 220px;
  }
}
</style>
