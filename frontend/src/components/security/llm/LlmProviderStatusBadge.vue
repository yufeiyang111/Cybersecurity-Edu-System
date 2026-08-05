<template>
  <BaseBadge :type="meta.tone">
    <span class="status-dot" :class="`status-dot--${meta.tone}`" />
    {{ meta.label }}
  </BaseBadge>
</template>

<script setup>
import { computed } from 'vue'
import { BaseBadge } from '@/components/ui'
import { providerStatus } from '@/features/security/llm/format'

const props = defineProps({ provider: { type: Object, required: true } })
const meta = computed(() => providerStatus(props.provider))
</script>

<style scoped lang="scss">
.status-dot { width: 6px; height: 6px; border-radius: 50%; background: currentColor; }
.status-dot--green { animation: pulse 1.6s ease-in-out infinite; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: .35; } }
</style>
