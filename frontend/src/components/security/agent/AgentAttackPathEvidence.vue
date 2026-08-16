<template>
  <section class="attack-path-evidence">
    <h5>已验证证据</h5>
    <div
      v-if="satisfiedEvidence.length"
      class="attack-path-evidence__chips"
    >
      <BaseBadge
        v-for="evidence in satisfiedEvidence"
        :key="evidence"
        type="green"
      >
        {{ evidence }}
      </BaseBadge>
    </div>
    <p
      v-else
      class="attack-path-evidence__muted"
    >
      暂无可确认的证据条件。
    </p>
  </section>

  <section class="attack-path-evidence">
    <h5>待补证据</h5>
    <div
      v-if="evidenceGaps.length"
      class="attack-path-evidence__gap-list"
    >
      <p
        v-for="gap in evidenceGaps"
        :key="gap"
      >
        <BaseIcon
          name="alert-triangle"
          :size="14"
        />
        {{ gap }}
      </p>
    </div>
    <p
      v-else
      class="attack-path-evidence__muted"
    >
      当前未记录证据缺口。
    </p>
  </section>

  <section
    v-if="authorizedScopes.length"
    class="attack-path-evidence"
  >
    <h5>授权核验范围</h5>
    <ul class="attack-path-evidence__scopes">
      <li
        v-for="scope in authorizedScopes"
        :key="`${scope.filePath}:${scope.startLine}-${scope.endLine}`"
      >
        {{ scope.filePath }} · 第 {{ scope.startLine }}-{{ scope.endLine }} 行
      </li>
    </ul>
  </section>
</template>

<script setup>
import {
  BaseBadge,
  BaseIcon,
} from '@/components/ui'

defineProps({
  satisfiedEvidence: {
    type: Array,
    default: () => [],
  },
  evidenceGaps: {
    type: Array,
    default: () => [],
  },
  authorizedScopes: {
    type: Array,
    default: () => [],
  },
})
</script>

<style scoped lang="scss">
.attack-path-evidence {
  margin-top: 10px;
}

.attack-path-evidence h5 {
  margin: 0 0 6px;
  color: #475569;
  font-size: 12px;
  font-weight: 600;
}

.attack-path-evidence__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
}

.attack-path-evidence__gap-list {
  display: grid;
  gap: 5px;
}

.attack-path-evidence__gap-list p {
  display: flex;
  align-items: flex-start;
  gap: 5px;
  margin: 0;
  color: #92400e;
  font-size: 12px;
  line-height: 1.5;
}

.attack-path-evidence__gap-list :deep(svg) {
  flex: none;
  margin-top: 2px;
}

.attack-path-evidence__scopes {
  display: grid;
  gap: 4px;
  margin: 0;
  padding: 0;
  color: #64748b;
  font-size: 11px;
  list-style: none;
  font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
  overflow-wrap: anywhere;
}

.attack-path-evidence__muted {
  margin: 0;
  color: #94a3b8;
  font-size: 12px;
  line-height: 1.55;
}
</style>
