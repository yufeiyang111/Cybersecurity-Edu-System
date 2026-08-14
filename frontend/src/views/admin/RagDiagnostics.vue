<template>
  <div class="rag-diagnostics-page">
    <RagDiagnosticsHeader
      :loading="runsState === 'loading'"
      @refresh="refreshRuns"
    />

    <div class="rag-diagnostics-grid">
      <RagEvaluationRuns
        :runs="runs"
        :total="runsPagination.total"
        :page="runsPagination.page"
        :pages="runsPagination.pages"
        :state="runsState"
        :error-message="runsError"
        :selected-run-id="selectedRun?.run?.id || null"
        @retry="refreshRuns"
        @select-run="selectRun"
        @change-page="changePage"
      />
      <RagEvaluationSummary
        :detail="selectedRun"
        :state="selectedRunState"
        :error-message="selectedRunError"
      />
    </div>

    <div class="rag-trace-grid">
      <RagTraceLookup
        :loading="traceState === 'loading'"
        @load-trace="handleLoadTrace"
      />
      <RagTraceSummary
        :trace="trace"
        :state="traceState"
        :error-message="traceError"
      />
    </div>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import RagDiagnosticsHeader from '@/components/admin/ragDiagnostics/RagDiagnosticsHeader.vue'
import RagEvaluationRuns from '@/components/admin/ragDiagnostics/RagEvaluationRuns.vue'
import RagEvaluationSummary from '@/components/admin/ragDiagnostics/RagEvaluationSummary.vue'
import RagTraceLookup from '@/components/admin/ragDiagnostics/RagTraceLookup.vue'
import RagTraceSummary from '@/components/admin/ragDiagnostics/RagTraceSummary.vue'
import { useRagDiagnostics } from '@/composables/admin/useRagDiagnostics'

const {
  runs,
  runsPagination,
  runsState,
  runsError,
  selectedRun,
  selectedRunState,
  selectedRunError,
  trace,
  traceState,
  traceError,
  loadRuns,
  loadRunDetail,
  loadTrace
} = useRagDiagnostics()

async function refreshRuns() {
  try {
    await loadRuns(1)
  } catch {
    // 错误状态已由 composable 归一化，页面不额外暴露服务端细节。
  }
}

async function changePage(page) {
  try {
    await loadRuns(page)
  } catch {
    // 错误状态已由 composable 归一化，页面不额外暴露服务端细节。
  }
}

async function selectRun(runId) {
  try {
    await loadRunDetail(runId)
  } catch {
    // 错误状态已由 composable 归一化，页面不额外暴露服务端细节。
  }
}

async function handleLoadTrace(traceId) {
  try {
    await loadTrace(traceId)
  } catch {
    // 错误状态已由 composable 归一化，页面不额外暴露服务端细节。
  }
}

onMounted(() => {
  void refreshRuns()
})
</script>

<style scoped lang="scss">
.rag-diagnostics-page {
  display: grid;
  max-width: 1320px;
  margin: 0 auto;
  gap: 20px;
}

.rag-diagnostics-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.05fr) minmax(0, 0.95fr);
  gap: 16px;
}

.rag-trace-grid {
  display: grid;
  grid-template-columns: minmax(260px, 0.32fr) minmax(0, 1fr);
  align-items: start;
  gap: 16px;
}

@media (min-width: 768px) and (max-width: 1200px) {
  .rag-diagnostics-page {
    gap: 16px;
  }

  .rag-diagnostics-grid,
  .rag-trace-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 767px) {
  .rag-diagnostics-page {
    gap: 12px;
  }

  .rag-diagnostics-grid,
  .rag-trace-grid {
    grid-template-columns: 1fr;
    gap: 12px;
  }
}
</style>
