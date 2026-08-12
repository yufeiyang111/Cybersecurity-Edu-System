<template>
  <div class="users-page">
    <div class="page-heading animate-fadeIn">
      <h2>用户管理</h2>
      <el-button
        type="primary"
        :loading="loading"
        @click="fetchUsers"
      >
        <el-icon>
          <Refresh />
        </el-icon>
        刷新数据
      </el-button>
    </div>

    <el-card
      class="panel-card list-card animate-fadeIn"
      shadow="never"
      style="animation-delay: 0.1s"
    >
      <template #header>
        <div class="panel-card__header">
          <span>用户列表</span>
          <span class="panel-card__header-count">共 {{ total }} 人</span>
        </div>
      </template>

      <div class="toolbar">
        <el-input
          v-model="keyword"
          placeholder="搜索用户名、昵称、邮箱..."
          clearable
          class="toolbar__search"
          @keyup.enter="handleSearch"
        >
          <template #prefix>
            <el-icon>
              <Search />
            </el-icon>
          </template>
        </el-input>

        <div class="toolbar__filters">
          <button
            v-for="option in roleOptions"
            :key="option.value"
            type="button"
            class="filter-chip"
            :class="{ 'filter-chip--active': filterRole === option.value }"
            @click="handleFilterChange(option.value)"
          >
            <span
              class="filter-chip__dot"
              :style="{ background: option.color }"
            />
            {{ option.label }}
          </button>
        </div>
      </div>

      <el-table
        :data="users"
        v-loading="loading"
        stripe
        class="users-table"
        @row-click="openDetail"
      >
        <template #empty>
          <div class="table-empty">暂无用户数据</div>
        </template>
        <el-table-column label="用户" min-width="220">
          <template #default="{ row }">
            <div class="user-cell">
              <el-avatar
                :size="34"
                :src="row.avatar_url || undefined"
                class="user-cell__avatar"
              >
                {{ getInitials(row) }}
              </el-avatar>
              <div class="user-cell__main">
                <span class="user-cell__name">{{ row.nickname || row.username || '未命名用户' }}</span>
                <span class="user-cell__username">@{{ row.username }}</span>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="邮箱" min-width="200">
          <template #default="{ row }">
            <span class="email-cell">
              <el-icon>
                <Message />
              </el-icon>
              {{ row.email || '-' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="角色" width="110">
          <template #default="{ row }">
            <span class="role-badge" :class="`role-badge--${row.role}`">
              <span class="role-badge__dot" />
              {{ getRoleText(row.role) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <div class="status-switch">
              <el-switch
                :model-value="row.is_active"
                size="small"
                @change="handleToggleStatus(row, $event)"
              />
              <span
                class="status-switch__text"
                :class="row.is_active ? 'is-on' : 'is-off'"
              >
                {{ row.is_active ? '正常' : '禁用' }}
              </span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="注册时间" width="150">
          <template #default="{ row }">
            <span class="time-cell">
              <el-icon>
                <Calendar />
              </el-icon>
              {{ formatDate(row.created_at) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right" align="center">
          <template #default="{ row }">
            <div class="action-buttons">
              <el-tooltip content="编辑" placement="top">
                <el-button
                  size="small"
                  circle
                  class="action-btn"
                  @click.stop="handleEdit(row)"
                >
                  <el-icon>
                    <Edit />
                  </el-icon>
                </el-button>
              </el-tooltip>
              <el-tooltip content="删除" placement="top">
                <el-button
                  size="small"
                  circle
                  type="danger"
                  class="action-btn"
                  @click.stop="handleDelete(row)"
                >
                  <el-icon>
                    <Delete />
                  </el-icon>
                </el-button>
              </el-tooltip>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-wrapper" v-if="total > pageSize">
        <el-pagination
          v-model:current-page="currentPage"
          :page-size="pageSize"
          :total="total"
          layout="prev, pager, next"
          @current-change="handlePageChange"
        />
      </div>
    </el-card>

    <!-- 详情弹窗 -->
    <el-dialog v-model="detailVisible" title="用户详情" width="640px">
      <div v-loading="detailLoading" class="user-detail">
        <template v-if="detail">
          <div class="user-detail__head">
            <el-avatar
              :size="56"
              :src="detail.user.avatar_url || undefined"
              class="user-detail__avatar"
            >
              {{ getInitials(detail.user) }}
            </el-avatar>
            <div class="user-detail__identity">
              <div class="user-detail__name">
                {{ detail.user.nickname || detail.user.username }}
                <span class="role-badge" :class="`role-badge--${detail.user.role}`">
                  <span class="role-badge__dot" />
                  {{ getRoleText(detail.user.role) }}
                </span>
              </div>
              <div class="user-detail__username">@{{ detail.user.username }}</div>
            </div>
            <span class="user-detail__status" :class="detail.user.is_active ? 'is-on' : 'is-off'">
              <i class="user-detail__status-dot" />
              {{ detail.user.is_active ? '正常' : '禁用' }}
            </span>
          </div>

          <div class="user-detail__info">
            <div class="info-item">
              <span class="info-item__label">邮箱</span>
              <span class="info-item__value">{{ detail.user.email || '-' }}</span>
            </div>
            <div class="info-item">
              <span class="info-item__label">注册时间</span>
              <span class="info-item__value">{{ formatDate(detail.user.created_at) }}</span>
            </div>
            <div class="info-item">
              <span class="info-item__label">最后登录</span>
              <span class="info-item__value">{{ formatDate(detail.user.last_login_at) || '从未登录' }}</span>
            </div>
            <div class="info-item">
              <span class="info-item__label">OAuth 绑定</span>
              <span class="info-item__value">
                {{ oauthText(detail.user) }}
              </span>
            </div>
          </div>

          <div class="user-detail__stats">
            <div
              v-for="stat in statItems"
              :key="stat.key"
              class="stat-chip"
            >
              <span class="stat-chip__value">{{ stat.value }}</span>
              <span class="stat-chip__label">{{ stat.label }}</span>
            </div>
          </div>

          <div class="user-detail__section">
            <h4>最近问答</h4>
            <div v-if="(detail.recent_records || []).length" class="mini-list">
              <div
                v-for="record in detail.recent_records"
                :key="record.id"
                class="mini-list__item"
              >
                <span class="mini-list__main">{{ record.question }}</span>
                <span class="mini-list__meta">
                  {{ formatDate(record.created_at) }}
                  <template v-if="record.feedback"> · {{ feedbackText(record.feedback) }}</template>
                </span>
              </div>
            </div>
            <div v-else class="muted-text">暂无问答记录</div>
          </div>

          <div class="user-detail__section">
            <h4>最近登录</h4>
            <div v-if="(detail.login_logs || []).length" class="mini-list">
              <div
                v-for="log in detail.login_logs"
                :key="log.id"
                class="mini-list__item"
              >
                <span class="login-dot" :class="log.status === 'success' ? 'is-success' : 'is-failed'" />
                <span class="mini-list__main">{{ log.ip_address || '未知 IP' }}</span>
                <span class="mini-list__meta">{{ formatDate(log.login_time) }}</span>
              </div>
            </div>
            <div v-else class="muted-text">暂无登录记录</div>
          </div>
        </template>
      </div>
    </el-dialog>

    <!-- 编辑弹窗 -->
    <el-dialog v-model="editDialogVisible" title="编辑用户" width="500px">
      <el-form ref="editFormRef" :model="editForm" label-width="80px">
        <el-form-item label="用户名">
          <el-input v-model="editForm.username" disabled />
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="editForm.email" disabled placeholder="邮箱暂不支持在管理后台修改" />
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="editForm.role">
            <el-option label="管理员" value="admin" />
            <el-option label="教师" value="teacher" />
            <el-option label="普通用户" value="user" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="editForm.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSave" :loading="saving">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { adminAPI } from '@/api'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Refresh, Edit, Delete, Message, Calendar } from '@element-plus/icons-vue'

const loading = ref(false)
const users = ref([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(10)
const keyword = ref('')
const filterRole = ref('')
const editDialogVisible = ref(false)
const saving = ref(false)
const editFormRef = ref()
const editForm = reactive({
  id: null,
  username: '',
  email: '',
  role: '',
  is_active: true
})

// 详情相关
const detailVisible = ref(false)
const detailLoading = ref(false)
const detail = ref(null)

const roleOptions = [
  { value: '', label: '全部', color: '#909399' },
  { value: 'admin', label: '管理员', color: '#cf222e' },
  { value: 'teacher', label: '教师', color: '#d29922' },
  { value: 'user', label: '普通用户', color: '#2563eb' }
]

const getRoleTagType = (role) => {
  const types = { admin: 'danger', teacher: 'warning', user: 'primary' }
  return types[role] || 'info'
}

const getRoleText = (role) => {
  const texts = { admin: '管理员', teacher: '教师', user: '普通用户' }
  return texts[role] || role
}

const getInitials = (row) => {
  const name = row.nickname || row.username || '?'
  return name[0].toUpperCase()
}

const oauthText = (user) => {
  const bindings = user.oauth_bindings || []
  if (!bindings.length) return user.oauth_provider ? user.oauth_provider : '未绑定'
  return bindings.map((b) => b.provider).join(', ')
}

const feedbackText = (fb) => {
  const texts = { good: '满意', neutral: '一般', bad: '不满意' }
  return texts[fb] || ''
}

const statItems = computed(() => {
  const stats = detail.value?.stats || {}
  return [
    { key: 'qa', label: '问答数', value: stats.qa_count || 0 },
    { key: 'conversation', label: '会话数', value: stats.conversation_count || 0 },
    { key: 'favorite', label: '收藏数', value: stats.favorite_count || 0 },
    { key: 'workspace', label: '工作区', value: stats.workspace_count || 0 },
    { key: 'memory', label: '记忆数', value: stats.memory_count || 0 }
  ]
})

const formatDate = (dateStr) => {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  const pad = (n) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

const fetchUsers = async () => {
  loading.value = true
  try {
    const res = await adminAPI.getUsers({
      page: currentPage.value,
      per_page: pageSize.value,
      keyword: keyword.value || undefined,
      role: filterRole.value || undefined
    })
    users.value = res.users || []
    total.value = res.total || 0
  } catch (error) {
    console.error('获取用户列表失败')
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  currentPage.value = 1
  fetchUsers()
}

const handleFilterChange = (role) => {
  filterRole.value = role
  handleSearch()
}

const handlePageChange = (page) => {
  currentPage.value = page
  fetchUsers()
}

const handleToggleStatus = async (row, value) => {
  try {
    await adminAPI.updateUser(row.id, { is_active: value })
    row.is_active = value
    ElMessage.success(value ? '已启用该用户' : '已禁用该用户')
  } catch (error) {
    ElMessage.error('状态切换失败')
  }
}

const handleEdit = (row) => {
  editForm.id = row.id
  editForm.username = row.username
  editForm.email = row.email
  editForm.role = row.role
  editForm.is_active = row.is_active
  editDialogVisible.value = true
}

const openDetail = async (row) => {
  detailVisible.value = true
  detailLoading.value = true
  try {
    const res = await adminAPI.getUserDetail(row.id)
    detail.value = res
  } catch (error) {
    detail.value = null
    ElMessage.error('加载用户详情失败')
  } finally {
    detailLoading.value = false
  }
}

const handleSave = async () => {
  saving.value = true
  try {
    await adminAPI.updateUser(editForm.id, {
      role: editForm.role,
      is_active: editForm.is_active
    })
    ElMessage.success('保存成功')
    editDialogVisible.value = false
    fetchUsers()
  } catch (error) {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除用户 "${row.username}" 吗？此操作不可恢复。`,
      '删除确认',
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    await adminAPI.deleteUser(row.id)
    ElMessage.success('删除成功')
    fetchUsers()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

onMounted(() => {
  fetchUsers()
})
</script>

<style lang="scss" scoped>
.users-page {
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

  // ==================== 内容卡片 ====================
  .panel-card {
    border-radius: 12px;
    border: 1px solid #e6e8eb;
    transition: transform 0.25s ease, box-shadow 0.25s ease;

    :deep(.el-card__header) {
      background: #fff;
      border-bottom-color: #e6e8eb;
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

  .panel-card__header-count {
    font-size: 12px;
    font-weight: 400;
    color: #909399;
  }

  // ==================== 列表区 ====================
  .list-card {
    :deep(.el-card__body) {
      padding: 0;
    }
  }

  .toolbar {
    display: flex;
    align-items: center;
    gap: 16px;
    flex-wrap: wrap;
    padding: 16px 20px;
    border-bottom: 1px solid #e6e8eb;
  }

  .toolbar__search {
    width: 280px;
  }

  .toolbar__filters {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }

  .filter-chip {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 14px;
    border: 1px solid #e6e8eb;
    border-radius: 999px;
    background: #fff;
    color: #606266;
    font-size: 13px;
    cursor: pointer;
    transition: all 0.2s ease;

    &:hover {
      border-color: #2ea44f;
      color: #2ea44f;
    }

    &--active {
      background: rgba(46, 164, 79, 0.08);
      border-color: #2ea44f;
      color: #2ea44f;
      font-weight: 600;
    }
  }

  .filter-chip__dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
  }

  // ==================== 表格 ====================
  .users-table {
    min-height: 620px;

    :deep(th.el-table__cell) {
      background: #fafbfc;
    }

    :deep(tbody tr) {
      transition: background 0.15s ease;
    }

    :deep(tbody tr:hover > td.el-table__cell) {
      background: #f6f8fa;
    }
  }

  .table-empty {
    padding: 80px 0;
    color: #909399;
    font-size: 13px;
  }

  .user-cell {
    display: flex;
    align-items: center;
    gap: 12px;
    min-width: 0;
  }

  .user-cell__avatar {
    flex-shrink: 0;
    background: #eef2ff;
    color: #4f46e5;
    font-weight: 600;
  }

  .user-cell__main {
    display: flex;
    flex-direction: column;
    min-width: 0;
  }

  .user-cell__name {
    font-weight: 600;
    color: #303133;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .user-cell__username {
    font-size: 12px;
    color: #909399;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .email-cell {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    color: #57606a;
    font-size: 13px;

    .el-icon {
      color: #909399;
    }
  }

  // 角色徽章
  .role-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 3px 10px;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 600;

    &__dot {
      width: 7px;
      height: 7px;
      border-radius: 50%;
    }

    &--admin {
      background: #fef2f2;
      color: #cf222e;

      .role-badge__dot {
        background: #cf222e;
      }
    }

    &--teacher {
      background: #fef3c7;
      color: #b45309;

      .role-badge__dot {
        background: #b45309;
      }
    }

    &--user {
      background: #eff6ff;
      color: #2563eb;

      .role-badge__dot {
        background: #2563eb;
      }
    }
  }

  // 状态开关
  .status-switch {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .status-switch__text {
    font-size: 13px;

    &.is-on {
      color: #2ea44f;
      font-weight: 600;
    }

    &.is-off {
      color: #cf222e;
    }
  }

  .time-cell {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    color: #909399;
    font-size: 13px;
    font-variant-numeric: tabular-nums;
  }

  // 操作按钮
  .action-buttons {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
  }

  .action-btn {
    border-color: #e6e8eb;
    color: #606266;
    transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;

    &:hover {
      transform: translateY(-2px);
      box-shadow: 0 4px 10px rgba(15, 23, 42, 0.12);
      border-color: #2ea44f;
      color: #2ea44f;
    }
  }

  .pagination-wrapper {
    display: flex;
    justify-content: center;
    padding: 16px 0;
  }

  // ==================== 用户详情弹窗 ====================
  .user-detail {
    min-height: 200px;
  }

  .user-detail__head {
    display: flex;
    align-items: center;
    gap: 14px;
    padding-bottom: 16px;
    border-bottom: 1px solid #e6e8eb;
  }

  .user-detail__avatar {
    flex-shrink: 0;
    background: #eef2ff;
    color: #4f46e5;
    font-size: 20px;
    font-weight: 600;
  }

  .user-detail__identity {
    flex: 1;
    min-width: 0;
  }

  .user-detail__name {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 18px;
    font-weight: 700;
    color: #1f2937;
  }

  .user-detail__username {
    margin-top: 2px;
    font-size: 13px;
    color: #909399;
  }

  .user-detail__status {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 12px;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 600;
    flex-shrink: 0;

    &.is-on {
      background: #d1fae5;
      color: #059669;
    }

    &.is-off {
      background: #fee2e2;
      color: #cf222e;
    }
  }

  .user-detail__status-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: currentColor;
  }

  .user-detail__info {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 12px 24px;
    padding: 16px 0;
    border-bottom: 1px solid #e6e8eb;

    @media (max-width: 560px) {
      grid-template-columns: 1fr;
    }
  }

  .info-item {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
  }

  .info-item__label {
    font-size: 12px;
    color: #909399;
  }

  .info-item__value {
    font-size: 14px;
    color: #303133;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .user-detail__stats {
    display: grid;
    grid-template-columns: repeat(5, minmax(0, 1fr));
    gap: 10px;
    padding: 16px 0;
    border-bottom: 1px solid #e6e8eb;

    @media (max-width: 560px) {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
  }

  .stat-chip {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 2px;
    padding: 10px 6px;
    border-radius: 10px;
    background: #f6f8fa;
    transition: background 0.2s ease, transform 0.2s ease;

    &:hover {
      background: #eff6ff;
      transform: translateY(-2px);
    }
  }

  .stat-chip__value {
    font-size: 18px;
    font-weight: 700;
    color: #1f2937;
    font-variant-numeric: tabular-nums;
  }

  .stat-chip__label {
    font-size: 12px;
    color: #909399;
  }

  .user-detail__section {
    padding-top: 16px;

    h4 {
      margin: 0 0 10px;
      font-size: 14px;
      color: #606266;
    }
  }

  .mini-list {
    display: flex;
    flex-direction: column;
    max-height: 180px;
    overflow-y: auto;
  }

  .mini-list__item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 10px;
    border-radius: 8px;
    transition: background 0.15s ease;

    &:hover {
      background: #f6f8fa;
    }
  }

  .mini-list__main {
    flex: 1;
    min-width: 0;
    font-size: 13px;
    color: #303133;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .mini-list__meta {
    flex-shrink: 0;
    font-size: 12px;
    color: #909399;
    font-variant-numeric: tabular-nums;
  }

  .login-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    flex-shrink: 0;

    &.is-success {
      background: #2ea44f;
    }

    &.is-failed {
      background: #cf222e;
    }
  }

  .muted-text {
    padding: 8px 0;
    font-size: 13px;
    color: #c8d2dd;
  }
}

@media (max-width: 768px) {
  .users-page {
    .page-heading {
      flex-wrap: wrap;

      .el-button {
        width: 100%;
      }
    }

    .toolbar__search {
      width: 100%;
    }
  }
}

@media (prefers-reduced-motion: reduce) {
  .users-page {
    .panel-card {
      transition: none;
    }

    .panel-card:hover {
      transform: none;
    }

    .filter-chip,
    .action-btn {
      transition: none;
    }
  }
}
</style>
