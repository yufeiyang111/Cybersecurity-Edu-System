<template>
  <BasePanel class="run-experience">
    <template #header>
      <div class="run-experience__head">
        <div>
          <h3>当前执行方式</h3>
          <p>{{ experience.label }}</p>
        </div>
        <BaseBadge :type="badgeType">
          {{ badgeLabel }}
        </BaseBadge>
      </div>
    </template>

    <p class="run-experience__description">
      {{ experience.description }}
    </p>
    <p
      v-if="experience.configurationNote"
      class="run-experience__configuration"
    >
      <strong>配置说明：</strong>{{ experience.configurationNote }}
    </p>
    <p class="run-experience__evidence">
      代码位置必须来自本轮授权的代码切片；知识库资料仅作为背景参考，不构成代码证据。
    </p>
  </BasePanel>
</template>

<script setup>
import { computed } from 'vue'
import { BaseBadge, BasePanel } from '@/components/ui'
import { resolveAgentRunExperience } from '@/features/security/agent/runExperience'

const props = defineProps({
  run: {
    type: Object,
    required: true
  },
  featureFlags: {
    type: Object,
    default: () => ({})
  },
  workspaceFeatureFlags: {
    type: Object,
    default: () => ({})
  }
})

const experience = computed(() => {
  return resolveAgentRunExperience(
    props.run,
    props.featureFlags,
    props.workspaceFeatureFlags
  )
})

const badgeType = computed(() => {
  if (experience.value.kind === 'agentic') {
    return 'blue'
  }
  if (experience.value.kind === 'workflow_limited') {
    return 'orange'
  }
  return 'gray'
})

const badgeLabel = computed(() => {
  if (experience.value.kind === 'agentic') {
    return '模型在环'
  }
  if (experience.value.kind === 'workflow_limited') {
    return '受限工作流'
  }
  return '确定性工作流'
})
</script>

<style scoped lang="scss">
.run-experience {
  margin-bottom: 12px;
}

.run-experience__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.run-experience__head h3 {
  margin: 0;
  color: #172033;
  font-size: 13px;
  font-weight: 600;
}

.run-experience__head p {
  margin: 4px 0 0;
  color: #52627a;
  font-size: 12px;
}

.run-experience__description {
  margin: 0;
  color: #40506a;
  font-size: 12.5px;
  line-height: 1.65;
}

.run-experience__configuration {
  margin: 8px 0 0;
  padding: 7px 9px;
  border-left: 3px solid #93c5fd;
  background: #eff6ff;
  color: #365274;
  font-size: 12px;
  line-height: 1.6;
}

.run-experience__evidence {
  margin: 8px 0 0;
  color: #52627a;
  font-size: 12px;
  line-height: 1.6;
}
</style>
