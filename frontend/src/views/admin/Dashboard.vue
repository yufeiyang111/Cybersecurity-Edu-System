<template>
  <div class="dashboard-page">
    <h2 class="page-title">系统概览</h2>

    <el-row :gutter="20" class="stats-row">
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-icon users">
            <el-icon :size="32"><User /></el-icon>
          </div>
          <div class="stat-content">
            <span class="stat-value">{{ stats.users?.total || 0 }}</span>
            <span class="stat-label">用户总数</span>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-icon knowledge">
            <el-icon :size="32"><Document /></el-icon>
          </div>
          <div class="stat-content">
            <span class="stat-value">{{ stats.knowledge?.total || 0 }}</span>
            <span class="stat-label">知识条目</span>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-icon qa">
            <el-icon :size="32"><ChatDotRound /></el-icon>
          </div>
          <div class="stat-content">
            <span class="stat-value">{{ stats.qa?.total_questions || 0 }}</span>
            <span class="stat-label">问答总数</span>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-icon vector">
            <el-icon :size="32"><Connection /></el-icon>
          </div>
          <div class="stat-content">
            <span class="stat-value">{{ stats.vector?.count || 0 }}</span>
            <span class="stat-label">向量索引</span>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20">
      <el-col :span="12">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>问答统计</span>
            </div>
          </template>
          <div class="qa-stats">
            <div class="qa-stat-item">
              <span>本周问答数：</span>
              <strong>{{ qaStats.recent_week || 0 }}</strong>
            </div>
            <div class="qa-stat-item">
              <span>平均响应时间：</span>
              <strong>{{ qaStats.avg_response_time || 0 }}秒</strong>
            </div>
          </div>
          <el-divider />
          <div class="feedback-stats">
            <h4>用户反馈</h4>
            <div class="feedback-bar">
              <div class="feedback-item good">
                <span>满意</span>
                <el-progress :percentage="getFeedbackPercent('good')" :color="'#67c23a'" />
                <span>{{ qaStats.feedback?.good || 0 }}</span>
              </div>
              <div class="feedback-item neutral">
                <span>一般</span>
                <el-progress :percentage="getFeedbackPercent('neutral')" :color="'#909399'" />
                <span>{{ qaStats.feedback?.neutral || 0 }}</span>
              </div>
              <div class="feedback-item bad">
                <span>不满意</span>
                <el-progress :percentage="getFeedbackPercent('bad')" :color="'#f56c6c'" />
                <span>{{ qaStats.feedback?.bad || 0 }}</span>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>知识图谱</span>
            </div>
          </template>
          <div class="graph-stats">
            <div class="graph-stat-item">
              <span>节点数：</span>
              <strong>{{ stats.graph?.node_count || 0 }}</strong>
            </div>
            <div class="graph-stat-item">
              <span>边数：</span>
              <strong>{{ stats.graph?.edge_count || 0 }}</strong>
            </div>
            <div class="graph-stat-item">
              <span>图密度：</span>
              <strong>{{ (stats.graph?.density || 0).toFixed(4) }}</strong>
            </div>
          </div>
          <el-divider />
          <div class="relation-types">
            <h4>关系类型统计</h4>
            <div class="relation-list">
              <el-tag
                v-for="(count, type) in stats.graph?.relation_types"
                :key="type"
                class="relation-tag"
              >
                {{ getRelationText(type) }}: {{ count }}
              </el-tag>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card class="mt-20">
      <template #header>
        <div class="card-header">
          <span>热门问答</span>
        </div>
      </template>
      <el-table :data="qaStats.hot_records" stripe>
        <el-table-column prop="question" label="问题" min-width="200">
          <template #default="{ row }">
            {{ row.question }}...
          </template>
        </el-table-column>
        <el-table-column prop="favorite_count" label="收藏数" width="100" />
        <el-table-column prop="feedback" label="反馈" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.feedback" :type="getFeedbackTagType(row.feedback)" size="small">
              {{ getFeedbackText(row.feedback) }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card class="mt-20">
      <template #header>
        <div class="card-header">
          <span>系统操作</span>
        </div>
      </template>
      <div class="actions">
        <el-button type="primary" @click="handleRebuildIndex" :loading="rebuilding">
          <el-icon><Refresh /></el-icon>
          重建向量索引
        </el-button>
        <el-button type="warning" @click="handleRebuildAllIndex" :loading="rebuildingAll">
          <el-icon><Refresh /></el-icon>
          重建所有索引
        </el-button>
        <el-button type="success" @click="handleInitSampleData" :loading="initing">
          <el-icon><Document /></el-icon>
          初始化示例数据
        </el-button>
      </div>
    </el-card>

    <el-card class="mt-20">
      <template #header>
        <div class="card-header">
          <span>最近问答</span>
        </div>
      </template>
      <el-table :data="recentQA" stripe>
        <el-table-column prop="question" label="问题" min-width="200" />
        <el-table-column prop="created_at" label="时间" width="180">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column prop="feedback" label="反馈" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.feedback" :type="getFeedbackTagType(row.feedback)" size="small">
              {{ getFeedbackText(row.feedback) }}
            </el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { adminAPI } from '@/api'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()

const loading = ref(false)
const stats = ref({})
const qaStats = ref({})
const recentQA = ref([])
const rebuilding = ref(false)
const rebuildingAll = ref(false)
const initing = ref(false)

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

const getFeedbackPercent = (type) => {
  const total = (qaStats.value.feedback?.good || 0) +
                (qaStats.value.feedback?.neutral || 0) +
                (qaStats.value.feedback?.bad || 0)
  if (total === 0) return 0
  return Math.round((qaStats.value.feedback?.[type] || 0) / total * 100)
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
    // 获取最近问答
    if (qaRes.hot_records && qaRes.hot_records.length > 0) {
      recentQA.value = qaRes.hot_records.slice(0, 5)
    }
  } catch (error) {
    console.error('获取统计数据失败')
  } finally {
    loading.value = false
  }
}

const handleRebuildIndex = async () => {
  rebuilding.value = true
  try {
    await adminAPI.rebuildVectorIndex()
    ElMessage.success('向量索引重建成功')
    fetchStats()
  } catch (error) {
    ElMessage.error('索引重建失败')
  } finally {
    rebuilding.value = false
  }
}

const handleRebuildAllIndex = async () => {
  rebuildingAll.value = true
  try {
    await adminAPI.rebuildAllIndex()
    ElMessage.success('所有索引重建成功')
    fetchStats()
  } catch (error) {
    ElMessage.error('索引重建失败')
  } finally {
    rebuildingAll.value = false
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
  .page-title {
    margin: 0 0 24px;
    font-size: 24px;
    color: #303133;
  }

  .stats-row {
    margin-bottom: 20px;

    .stat-card {
      display: flex;
      align-items: center;
      gap: 16px;

      .stat-icon {
        width: 64px;
        height: 64px;
        border-radius: 12px;
        display: flex;
        align-items: center;
        justify-content: center;
        color: #fff;

        &.users { background: linear-gradient(135deg, #10b981, #059669); }
        &.knowledge { background: linear-gradient(135deg, #f093fb, #f5576c); }
        &.qa { background: linear-gradient(135deg, #10b981, #14b8a6); }
        &.vector { background: linear-gradient(135deg, #43e97b, #38f9d7); }
      }

      .stat-content {
        display: flex;
        flex-direction: column;

        .stat-value {
          font-size: 28px;
          font-weight: 600;
          color: #303133;
        }

        .stat-label {
          font-size: 14px;
          color: #909399;
        }
      }
    }
  }

  .card-header {
    font-weight: 600;
  }

  .mt-20 {
    margin-top: 20px;
  }

  .qa-stats, .graph-stats {
    display: flex;
    gap: 32px;

    .qa-stat-item, .graph-stat-item {
      span {
        color: #909399;
      }
      strong {
        color: #10b981;
        font-size: 18px;
      }
    }
  }

  .feedback-stats, .relation-types {
    h4 {
      margin: 0 0 12px;
      font-size: 14px;
      color: #606266;
    }

    .feedback-bar {
      .feedback-item {
        display: flex;
        align-items: center;
        gap: 12px;
        margin-bottom: 8px;

        span:first-child {
          width: 60px;
          color: #606266;
        }

        .el-progress {
          flex: 1;
        }

        span:last-child {
          width: 40px;
          text-align: right;
          color: #909399;
        }
      }
    }

    .relation-list {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;

      .relation-tag {
        cursor: pointer;
        &:hover {
          opacity: 0.8;
        }
      }
    }
  }

  .actions {
    display: flex;
    gap: 12px;
  }
}
</style>
