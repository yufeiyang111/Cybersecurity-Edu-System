<template>
  <section class="metric-grid" aria-label="项目关键指标">
    <template v-if="loading || findingsLoading">
      <div v-for="index in 5" :key="index" class="metric-card metric-card--skeleton">
        <el-skeleton animated :rows="2" />
      </div>
    </template>
    <template v-else>
      <article class="metric-card metric-card--risk">
        <span class="metric-icon"><el-icon><DataLine /></el-icon></span>
        <div class="metric-copy">
          <span class="metric-label">综合风险分</span>
          <strong class="metric-value">{{ riskScore }}</strong>
          <span class="metric-foot">当前选中任务</span>
        </div>
      </article>
      <article class="metric-card" :class="highRiskCount ? 'metric-card--danger' : 'metric-card--success'">
        <span class="metric-icon"><el-icon><Warning /></el-icon></span>
        <div class="metric-copy">
          <span class="metric-label">高危及以上发现</span>
          <strong class="metric-value">{{ highRiskCount }}</strong>
          <span class="metric-foot">{{ highRiskCount ? '需要优先处理' : '当前无阻断项' }}</span>
        </div>
      </article>
      <article class="metric-card">
        <span class="metric-icon"><el-icon><List /></el-icon></span>
        <div class="metric-copy">
          <span class="metric-label">风险发现总数</span>
          <strong class="metric-value">{{ findingsTotal }}</strong>
          <span class="metric-foot">当前任务结果</span>
        </div>
      </article>
      <article class="metric-card metric-card--success">
        <span class="metric-icon"><el-icon><Document /></el-icon></span>
        <div class="metric-copy">
          <span class="metric-label">修复建议已审核</span>
          <strong class="metric-value">{{ suggestionValue }}</strong>
          <span class="metric-foot">等待人工处理</span>
        </div>
      </article>
      <article class="metric-card metric-card--purple">
        <span class="metric-icon"><el-icon><Refresh /></el-icon></span>
        <div class="metric-copy">
          <span class="metric-label">扫描任务</span>
          <strong class="metric-value">{{ taskCount }}</strong>
          <span class="metric-foot">项目累计任务</span>
        </div>
      </article>
    </template>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { DataLine, Document, List, Refresh, Warning } from '@element-plus/icons-vue'

const props = defineProps({
  loading: { type: Boolean, default: false },
  findingsLoading: { type: Boolean, default: false },
  avgRiskScore: { type: Number, default: null },
  highRiskCount: { type: Number, default: 0 },
  findingsTotal: { type: Number, default: 0 },
  suggestionStats: { type: Object, default: () => ({ total: 0, reviewed: 0 }) },
  taskCount: { type: Number, default: 0 }
})

const riskScore = computed(() => (
  props.avgRiskScore === null ? '-' : Math.round(props.avgRiskScore)
))
const suggestionValue = computed(() => (
  props.suggestionStats.total
    ? `${props.suggestionStats.reviewed} / ${props.suggestionStats.total}`
    : '0 / 0'
))
</script>

<style scoped lang="scss">
.metric-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 10px;
  margin-top: 12px;
}

.metric-card {
  position: relative;
  display: flex;
  min-height: 106px;
  align-items: flex-start;
  gap: 10px;
  padding: 15px;
  overflow: hidden;
  border: 1px solid #dfe6ef;
  border-radius: 9px;
  background: #ffffff;
  box-shadow: 0 3px 12px rgba(21, 40, 75, 0.04);
  transition: border-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease;
}

.metric-card:hover {
  border-color: #c4d3e4;
  box-shadow: 0 10px 22px rgba(21, 40, 75, 0.08);
  transform: translateY(-2px);
}

.metric-card::after {
  position: absolute;
  right: 0;
  bottom: 0;
  left: 0;
  height: 3px;
  background: #2563eb;
  content: "";
}

.metric-card--risk::after {
  background: #c8751b;
}

.metric-card--danger::after {
  background: #c94343;
}

.metric-card--success::after {
  background: #16834d;
}

.metric-card--purple::after {
  background: #7654b9;
}

.metric-card--skeleton {
  padding: 14px;
}

.metric-icon {
  display: inline-flex;
  width: 32px;
  height: 32px;
  flex: 0 0 32px;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  color: #2563eb;
  background: #eff6ff;
}

.metric-card--risk .metric-icon {
  color: #c8751b;
  background: #fff7e8;
}

.metric-card--danger .metric-icon {
  color: #c94343;
  background: #fff1f1;
}

.metric-card--success .metric-icon {
  color: #16834d;
  background: #ecfdf3;
}

.metric-card--purple .metric-icon {
  color: #7654b9;
  background: #f5f1ff;
}

.metric-icon .el-icon {
  font-size: 17px;
}

.metric-copy {
  min-width: 0;
}

.metric-label {
  display: block;
  color: #52627a;
  font-size: 11.5px;
  white-space: nowrap;
}

.metric-value {
  display: block;
  margin-top: 4px;
  color: #142238;
  font-size: 23px;
  font-weight: 750;
  letter-spacing: -0.03em;
  line-height: 1.05;
}

.metric-card--risk .metric-value {
  color: #c8751b;
}

.metric-card--danger .metric-value {
  color: #c94343;
}

.metric-card--success .metric-value {
  color: #16834d;
}

.metric-foot {
  display: block;
  margin-top: 5px;
  color: #7e8da3;
  font-size: 10.5px;
  white-space: nowrap;
}

@media (max-width: 1200px) {
  .metric-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 760px) {
  .metric-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 8px;
  }

  .metric-card {
    min-height: 98px;
    padding: 12px;
  }

  .metric-icon {
    width: 29px;
    height: 29px;
    flex-basis: 29px;
  }

  .metric-value {
    font-size: 21px;
  }
}
</style>
