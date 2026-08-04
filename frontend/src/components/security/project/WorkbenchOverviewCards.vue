<template>
  <section class="stats">
    <article class="stat-card s-red">
      <div class="s-head">
        <span class="s-label">严重漏洞</span>
        <span class="s-icon"><el-icon><WarningFilled /></el-icon></span>
      </div>
      <div class="s-num">{{ loading ? '—' : totals.critical }}</div>
      <div class="s-trend">需优先处理</div>
    </article>

    <article class="stat-card s-orange">
      <div class="s-head">
        <span class="s-label">高危漏洞</span>
        <span class="s-icon"><el-icon><Warning /></el-icon></span>
      </div>
      <div class="s-num">{{ loading ? '—' : totals.high }}</div>
      <div class="s-trend">建议尽快修复</div>
    </article>

    <article class="stat-card s-yellow">
      <div class="s-head">
        <span class="s-label">中危漏洞</span>
        <span class="s-icon"><el-icon><InfoFilled /></el-icon></span>
      </div>
      <div class="s-num">{{ loading ? '—' : totals.medium }}</div>
      <div class="s-trend">安排计划修复</div>
    </article>

    <article class="stat-card s-blue">
      <div class="s-head">
        <span class="s-label">扫描项目</span>
        <span class="s-icon"><el-icon><Files /></el-icon></span>
      </div>
      <div class="s-num">{{ loading ? '—' : totalProjects }}</div>
      <div class="s-trend">累计 {{ loading ? '—' : totalScans }} 次扫描</div>
    </article>
  </section>
</template>

<script setup>
import { Files, InfoFilled, Warning, WarningFilled } from '@element-plus/icons-vue'

defineProps({
  totals: { type: Object, default: () => ({ critical: 0, high: 0, medium: 0 }) },
  totalProjects: { type: Number, default: 0 },
  totalScans: { type: Number, default: 0 },
  loading: { type: Boolean, default: false }
})
</script>

<style scoped lang="scss">
.stats {
  margin-top: 20px;
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
}

.stat-card {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 16px;

  .s-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .s-label {
    font-size: 13px;
    color: #475569;
  }

  .s-icon {
    width: 36px;
    height: 36px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;

    .el-icon {
      font-size: 18px;
    }
  }

  .s-num {
    margin-top: 12px;
    font-size: 28px;
    font-weight: 700;
    font-variant-numeric: tabular-nums;
  }

  .s-trend {
    margin-top: 4px;
    font-size: 12px;
    color: #94a3b8;
  }
}

.s-red {
  .s-icon { background: #fee2e2; color: #dc2626; }
  .s-num { color: #dc2626; }
}

.s-orange {
  .s-icon { background: #ffedd5; color: #ea580c; }
  .s-num { color: #ea580c; }
}

.s-yellow {
  .s-icon { background: #fef9c3; color: #ca8a04; }
  .s-num { color: #ca8a04; }
}

.s-blue {
  .s-icon { background: #dbeafe; color: #2563eb; }
  .s-num { color: #2563eb; }
}

@media (max-width: 1200px) {
  .stats {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 560px) {
  .stats {
    grid-template-columns: 1fr;
  }
}
</style>
