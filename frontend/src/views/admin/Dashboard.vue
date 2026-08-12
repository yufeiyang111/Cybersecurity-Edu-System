<template>
  <div class="dashboard-page">
    <div class="page-heading animate-fadeIn">
      <h2>系统概览</h2>
      <el-button
        type="primary"
        :loading="loading"
        @click="fetchStats"
      >
        <el-icon>
          <Refresh />
        </el-icon>
        刷新数据
      </el-button>
    </div>

    <el-row :gutter="20" class="stats-row">
      <el-col
        v-for="(card, index) in statCards"
        :key="card.key"
        :xs="24"
        :sm="12"
        :md="6"
        class="stats-row__col animate-fadeIn"
        :style="{ animationDelay: `${0.08 + index * 0.08}s` }"
      >
        <StatCard
          :icon="card.icon"
          :icon-bg="card.iconBg"
          :icon-color="card.iconColor"
          :label="card.label"
          :display="card.state.display"
          :sub="card.sub"
          :to="card.to"
        />
      </el-col>
    </el-row>

    <el-row :gutter="20" class="middle-row">
      <el-col
        :xs="24"
        :md="12"
        class="middle-row__col animate-fadeIn"
        style="animation-delay: 0.42s"
      >
        <el-card class="panel-card" shadow="never">
          <template #header>
            <div class="panel-card__header">
              <span>问答统计</span>
              <span class="panel-card__header-icon">
                <el-icon>
                  <TrendCharts />
                </el-icon>
              </span>
            </div>
          </template>

          <div class="metric-list">
            <div class="metric-item">
              <div class="metric-item__icon metric-item__icon--sky">
                <el-icon>
                  <TrendCharts />
                </el-icon>
              </div>
              <div class="metric-item__main">
                <span class="metric-item__label">本周问答数</span>
                <span class="metric-item__value">{{ weekStat.display }}</span>
              </div>
            </div>
            <div class="metric-item">
              <div class="metric-item__icon metric-item__icon--amber">
                <el-icon>
                  <Clock />
                </el-icon>
              </div>
              <div class="metric-item__main">
                <span class="metric-item__label">平均响应时间</span>
                <span class="metric-item__value">{{ avgStat.display }} 秒</span>
              </div>
            </div>
          </div>

          <el-divider />

          <div class="chart-block">
            <h4>问答与会话构成</h4>
            <HBarChart :items="qaComposition" />
          </div>
        </el-card>
      </el-col>

      <el-col
        :xs="24"
        :md="12"
        class="middle-row__col animate-fadeIn"
        style="animation-delay: 0.5s"
      >
        <el-card class="panel-card" shadow="never">
          <template #header>
            <div class="panel-card__header">
              <span>知识图谱</span>
              <span class="panel-card__header-icon">
                <el-icon>
                  <Share />
                </el-icon>
              </span>
            </div>
          </template>

          <div class="metric-list">
            <div
              v-for="item in graphMetrics"
              :key="item.label"
              class="metric-item"
            >
              <div
                class="metric-item__icon"
                :style="{ background: item.bg, color: item.color }"
              >
                <el-icon>
                  <component :is="item.icon" />
                </el-icon>
              </div>
              <div class="metric-item__main">
                <span class="metric-item__label">{{ item.label }}</span>
                <span class="metric-item__value">{{ item.state.display }}</span>
              </div>
            </div>
          </div>

          <el-divider />

          <div class="chart-block">
            <h4>关系类型统计</h4>
            <HBarChart :items="relationItems" />
            <div
              v-if="!relationItems.length"
              class="chart-block__empty"
            >
              暂无关系数据
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" class="charts-row">
      <el-col
        :xs="24"
        :md="8"
        class="charts-row__col animate-fadeIn"
        style="animation-delay: 0.58s"
      >
        <el-card class="panel-card" shadow="never">
          <template #header>
            <div class="panel-card__header">
              <span>用户活跃度</span>
              <span class="panel-card__header-icon">
                <el-icon>
                  <User />
                </el-icon>
              </span>
            </div>
          </template>
          <DonutChart
            :segments="userSegments"
            :center-value="activePercent"
            center-label="活跃占比"
          />
        </el-card>
      </el-col>

      <el-col
        :xs="24"
        :md="8"
        class="charts-row__col animate-fadeIn"
        style="animation-delay: 0.66s"
      >
        <el-card class="panel-card" shadow="never">
          <template #header>
            <div class="panel-card__header">
              <span>知识发布率</span>
              <span class="panel-card__header-icon">
                <el-icon>
                  <Document />
                </el-icon>
              </span>
            </div>
          </template>
          <DonutChart
            :segments="knowledgeSegments"
            :center-value="publishedPercent"
            center-label="已发布占比"
          />
        </el-card>
      </el-col>

      <el-col
        :xs="24"
        :md="8"
        class="charts-row__col animate-fadeIn"
        style="animation-delay: 0.74s"
      >
        <el-card class="panel-card" shadow="never">
          <template #header>
            <div class="panel-card__header">
              <span>用户反馈分布</span>
              <span class="panel-card__header-icon">
                <el-icon>
                  <CircleCheck />
                </el-icon>
              </span>
            </div>
          </template>
          <DonutChart
            :segments="feedbackSegments"
            :center-value="feedbackTotal"
            center-label="总反馈"
          />
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" class="tables-row">
      <el-col
        :xs="24"
        :md="12"
        class="tables-row__col animate-fadeIn"
        style="animation-delay: 0.82s"
      >
        <el-card class="panel-card" shadow="never">
          <template #header>
            <div class="panel-card__header">
              <span>热门问答</span>
              <span class="panel-card__header-icon">
                <el-icon>
                  <Star />
                </el-icon>
              </span>
            </div>
          </template>
          <el-table :data="qaStats.hot_records || []" stripe>
            <template #empty>
              <div class="table-empty">暂无数据</div>
            </template>
            <el-table-column prop="question" label="问题" min-width="180">
              <template #default="{ row }">
                {{ row.question }}...
              </template>
            </el-table-column>
            <el-table-column prop="favorite_count" label="收藏数" width="90" />
            <el-table-column prop="feedback" label="反馈" width="90">
              <template #default="{ row }">
                <el-tag v-if="row.feedback" :type="getFeedbackTagType(row.feedback)" size="small">
                  {{ getFeedbackText(row.feedback) }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>

      <el-col
        :xs="24"
        :md="12"
        class="tables-row__col animate-fadeIn"
        style="animation-delay: 0.9s"
      >
        <el-card class="panel-card" shadow="never">
          <template #header>
            <div class="panel-card__header">
              <span>最近问答</span>
              <span class="panel-card__header-icon">
                <el-icon>
                  <ChatDotRound />
                </el-icon>
              </span>
            </div>
          </template>
          <el-table :data="recentQA" stripe>
            <template #empty>
              <div class="table-empty">暂无数据</div>
            </template>
            <el-table-column prop="question" label="问题" min-width="180" />
            <el-table-column prop="created_at" label="时间" width="160">
              <template #default="{ row }">
                {{ formatTime(row.created_at) }}
              </template>
            </el-table-column>
            <el-table-column prop="feedback" label="反馈" width="90">
              <template #default="{ row }">
                <el-tag v-if="row.feedback" :type="getFeedbackTagType(row.feedback)" size="small">
                  {{ getFeedbackText(row.feedback) }}
                </el-tag>
                <span v-else>-</span>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <el-card
      class="panel-card mt-20 animate-fadeIn"
      shadow="never"
      style="animation-delay: 0.98s"
    >
      <template #header>
        <div class="panel-card__header">
          <span>系统操作</span>
          <span class="panel-card__header-icon">
            <el-icon>
              <Tools />
            </el-icon>
          </span>
        </div>
      </template>
      <div class="actions">
        <VectorRebuildPanel class="vector-rebuild-panel" />
        <el-button type="success" @click="handleInitSampleData" :loading="initing">
          <el-icon>
            <Document />
          </el-icon>
          初始化示例数据
        </el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { adminAPI } from '@/api'
import { ElMessage } from 'element-plus'
import {
  User,
  Document,
  ChatDotRound,
  Connection,
  Refresh,
  TrendCharts,
  Clock,
  Share,
  Link,
  PieChart,
  CircleCheck,
  Star,
  Tools
} from '@element-plus/icons-vue'
import StatCard from '@/components/admin/dashboard/StatCard.vue'
import DonutChart from '@/components/admin/dashboard/DonutChart.vue'
import HBarChart from '@/components/admin/dashboard/HBarChart.vue'
import VectorRebuildPanel from '@/components/admin/dashboard/VectorRebuildPanel.vue'
import { useAnimatedNumber } from '@/composables/admin/useAnimatedNumber'

const loading = ref(false)
const stats = ref({})
const qaStats = ref({})
const recentQA = ref([])
const initing = ref(false)

const weekStat = useAnimatedNumber(() => qaStats.value.recent_week || 0)
const avgStat = useAnimatedNumber(() => qaStats.value.avg_response_time || 0, { decimals: 2 })
const nodeStat = useAnimatedNumber(() => stats.value.graph?.node_count || 0)
const edgeStat = useAnimatedNumber(() => stats.value.graph?.edge_count || 0)
const densityStat = useAnimatedNumber(() => stats.value.graph?.density || 0, { decimals: 4 })

const statCards = computed(() => [
  {
    key: 'users',
    label: '用户总数',
    icon: User,
    iconBg: '#eef2ff',
    iconColor: '#4f46e5',
    state: useAnimatedNumber(() => stats.value.users?.total || 0),
    sub: `活跃 ${stats.value.users?.active || 0} 人`,
    to: '/admin/users'
  },
  {
    key: 'knowledge',
    label: '知识条目',
    icon: Document,
    iconBg: '#fdf2f8',
    iconColor: '#db2777',
    state: useAnimatedNumber(() => stats.value.knowledge?.total || 0),
    sub: `已发布 ${stats.value.knowledge?.published || 0} 条`,
    to: '/admin/knowledge'
  },
  {
    key: 'qa',
    label: '问答总数',
    icon: ChatDotRound,
    iconBg: '#e0f2fe',
    iconColor: '#0284c7',
    state: useAnimatedNumber(() => stats.value.qa?.total_questions || 0),
    sub: `会话 ${stats.value.qa?.total_conversations || 0} 个`
  },
  {
    key: 'vector',
    label: '向量索引',
    icon: Connection,
    iconBg: '#d1fae5',
    iconColor: '#059669',
    state: useAnimatedNumber(() => stats.value.vector?.count || 0),
    sub: `图节点 ${stats.value.graph?.node_count || 0} 个`
  }
])

const graphMetrics = [
  { label: '节点数', icon: Share, bg: '#d1fae5', color: '#059669', state: nodeStat },
  { label: '边数', icon: Link, bg: '#e0f2fe', color: '#0284c7', state: edgeStat },
  { label: '图密度', icon: PieChart, bg: '#fef3c7', color: '#b45309', state: densityStat }
]

const qaComposition = computed(() => [
  {
    label: '问答总数',
    value: stats.value.qa?.total_questions || 0,
    color: '#0284c7'
  },
  {
    label: '会话总数',
    value: stats.value.qa?.total_conversations || 0,
    color: '#38bdf8'
  }
])

const RELATION_COLORS = ['#10b981', '#0ea5e9', '#8b5cf6', '#f59e0b', '#ef4444', '#06b6d4', '#d946ef']

const relationItems = computed(() => {
  const types = stats.value.graph?.relation_types || {}
  return Object.entries(types).map(([type, count], index) => ({
    label: getRelationText(type),
    value: count,
    color: RELATION_COLORS[index % RELATION_COLORS.length]
  }))
})

const percentOf = (value, total) => {
  if (!total) return '0%'
  return `${Math.round(value / total * 100)}%`
}

const activePercent = computed(() => {
  const total = stats.value.users?.total || 0
  return percentOf(stats.value.users?.active || 0, total)
})

const userSegments = computed(() => {
  const total = stats.value.users?.total || 0
  const active = stats.value.users?.active || 0
  return [
    { label: '活跃', value: active, color: '#2ea44f' },
    { label: '非活跃', value: Math.max(0, total - active), color: '#f0f2f5' }
  ]
})

const publishedPercent = computed(() => {
  const total = stats.value.knowledge?.total || 0
  return percentOf(stats.value.knowledge?.published || 0, total)
})

const knowledgeSegments = computed(() => {
  const total = stats.value.knowledge?.total || 0
  const published = stats.value.knowledge?.published || 0
  return [
    { label: '已发布', value: published, color: '#0284c7' },
    { label: '未发布', value: Math.max(0, total - published), color: '#f0f2f5' }
  ]
})

const feedbackTotal = computed(() => {
  const fb = qaStats.value.feedback || {}
  return (fb.good || 0) + (fb.neutral || 0) + (fb.bad || 0)
})

const feedbackSegments = computed(() => {
  const fb = qaStats.value.feedback || {}
  return [
    { label: '满意', value: fb.good || 0, color: '#2ea44f' },
    { label: '一般', value: fb.neutral || 0, color: '#9ca3af' },
    { label: '不满意', value: fb.bad || 0, color: '#cf222e' }
  ]
})

const getRelationText = (rel) => {
  const texts = {
    'is_a': '包含关系',
    'part_of': '组成关系',
    'uses': '使用关系',
    'caused_by': '因果关系',
    'related_to': '相关关系',
    'depends_on': '依赖关系',
    'contrasts_with': '对比关系'
  }
  return texts[rel] || rel
}

const getFeedbackTagType = (fb) => {
  const types = { good: 'success', neutral: 'info', bad: 'danger' }
  return types[fb]
}

const getFeedbackText = (fb) => {
  const texts = { good: '满意', neutral: '一般', bad: '不满意' }
  return texts[fb]
}

const formatTime = (time) => {
  if (!time) return '-'
  const date = new Date(time)
  return date.toLocaleString('zh-CN')
}

const fetchStats = async () => {
  loading.value = true
  try {
    const [overviewRes, qaRes] = await Promise.all([
      adminAPI.getOverviewStats(),
      adminAPI.getQAStats()
    ])
    stats.value = overviewRes
    qaStats.value = qaRes
    if (qaRes.hot_records && qaRes.hot_records.length > 0) {
      recentQA.value = qaRes.hot_records.slice(0, 5)
    }
  } catch (error) {
    console.error('获取统计数据失败')
  } finally {
    loading.value = false
  }
}

const handleInitSampleData = async () => {
  initing.value = true
  try {
    const res = await adminAPI.initSampleData()
    ElMessage.success('示例数据初始化成功')
    if (res.results) {
      console.log('初始化结果:', res.results)
    }
    fetchStats()
  } catch (error) {
    ElMessage.error('初始化失败')
  } finally {
    initing.value = false
  }
}

onMounted(() => {
  fetchStats()
})
</script>

<style lang="scss" scoped>
.dashboard-page {
  // ==================== 页面标题行 ====================
  .page-heading {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    margin-bottom: 16px;

    h2 {
      margin: 0;
      font-size: 20px;
      font-weight: 700;
      color: #1f2937;
    }
  }

  // ==================== 统计卡片行 ====================
  .stats-row {
    margin-bottom: 20px;

    .stats-row__col {
      margin-bottom: 20px;

      @media (min-width: 768px) {
        margin-bottom: 0;
      }
    }
  }

  // ==================== 内容卡片 ====================
  .panel-card {
    height: 100%;
    border-radius: 12px;
    border: 1px solid #e6e8eb;
    transition: transform 0.25s ease, box-shadow 0.25s ease;

    :deep(.el-card__header) {
      background: #fff;
      border-bottom-color: #e6e8eb;
    }

    :deep(.el-card__body) {
      display: flex;
      flex-direction: column;
      justify-content: center;
    }

    &:hover {
      transform: translateY(-3px);
      box-shadow: 0 12px 28px rgba(15, 23, 42, 0.08);
    }
  }

  .panel-card__header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-weight: 600;
    color: #303133;
  }

  .panel-card__header-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    border-radius: 8px;
    background: #d1fae5;
    color: #059669;
    font-size: 15px;
  }

  // ==================== 指标列表 ====================
  .metric-list {
    display: flex;
    flex-direction: column;
    gap: 14px;
  }

  .metric-item {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .metric-item__icon {
    width: 40px;
    height: 40px;
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 18px;

    &--sky {
      background: #e0f2fe;
      color: #0284c7;
    }

    &--amber {
      background: #fef3c7;
      color: #b45309;
    }
  }

  .metric-item__main {
    display: flex;
    flex-direction: column;
  }

  .metric-item__label {
    font-size: 13px;
    color: #909399;
  }

  .metric-item__value {
    margin-top: 2px;
    font-size: 20px;
    font-weight: 600;
    color: #1f2937;
    font-variant-numeric: tabular-nums;
  }

  // ==================== 图表区块 ====================
  .chart-block {
    h4 {
      margin: 0 0 12px;
      font-size: 14px;
      color: #606266;
    }
  }

  .chart-block__empty {
    padding: 16px 0;
    text-align: center;
    font-size: 13px;
    color: #909399;
  }

  .charts-row {
    margin-top: 20px;

    .charts-row__col {
      margin-bottom: 20px;

      @media (min-width: 768px) {
        margin-bottom: 0;
      }
    }
  }

  .tables-row {
    margin-top: 20px;

    .tables-row__col {
      margin-bottom: 20px;

      @media (min-width: 768px) {
        margin-bottom: 0;
      }
    }

    .panel-card {
      :deep(.el-card__body) {
        justify-content: flex-start;
      }

      :deep(.el-table) {
        min-height: 400px;
      }
    }
  }

  .table-empty {
    padding: 60px 0;
    color: #909399;
    font-size: 13px;
  }

  // ==================== 操作区 ====================
  .actions {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
    align-items: flex-start;

    .el-button {
      transition: transform 0.2s ease, box-shadow 0.2s ease;

      &:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 14px rgba(15, 23, 42, 0.12);
      }
    }

    .vector-rebuild-panel {
      width: 100%;
    }
  }

  .mt-20 {
    margin-top: 20px;
  }
}

@media (max-width: 768px) {
  .dashboard-page {
    .page-heading {
      flex-wrap: wrap;

      .el-button {
        width: 100%;
      }
    }
  }
}

@media (prefers-reduced-motion: reduce) {
  .dashboard-page {
    .panel-card {
      transition: none;
    }

    .panel-card:hover {
      transform: none;
    }

    .actions .el-button {
      transition: none;
    }
  }
}
</style>
