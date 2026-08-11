<template>
  <div class="history-list">
    <div v-if="items.length" class="history-head">
      <span class="history-count">共 {{ items.length }} 条记录</span>
      <el-popconfirm
        title="确认清空全部问答历史？"
        confirm-button-text="清空"
        cancel-button-text="取消"
        @confirm="$emit('clear')"
      >
        <template #reference>
          <el-button text size="small" type="danger" :disabled="!items.length">
            清空
          </el-button>
        </template>
      </el-popconfirm>
    </div>

    <div v-if="items.length" class="history-items">
      <div
        v-for="item in items"
        :key="item.id"
        class="history-item"
        @click="$emit('select', item)"
      >
        <div class="history-item-head">
          <el-tag
            size="small"
            :type="item.mode === 'global' ? 'info' : 'warning'"
            effect="plain"
          >
            {{ item.mode === 'global' ? '全局' : '实体' }}
          </el-tag>
          <span class="history-query">{{ item.query }}</span>
          <span class="history-time">{{ formatTime(item.createdAt) }}</span>
        </div>
        <p class="history-preview">{{ previewText(item.answer) }}</p>
        <button
          type="button"
          class="history-delete"
          title="删除该条记录"
          @click.stop="$emit('remove', item.id)"
        >
          <el-icon><Delete /></el-icon>
        </button>
      </div>
    </div>

    <el-empty
      v-else
      description="暂无问答历史，先去问一个问题吧"
      :image-size="60"
    />
  </div>
</template>

<script setup>
import { Delete } from '@element-plus/icons-vue'

defineProps({
  items: { type: Array, default: () => [] }
})
defineEmits(['select', 'remove', 'clear'])

const formatTime = (value) => {
  if (!value) return ''
  const date = new Date(value)
  const pad = (n) => String(n).padStart(2, '0')
  return `${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

const previewText = (text) => {
  if (!text) return ''
  const clean = text.replace(/[#*`>\-\n]/g, ' ').replace(/\s+/g, ' ').trim()
  return clean.length > 80 ? `${clean.slice(0, 80)}...` : clean
}
</script>

<style scoped lang="scss">
.history-list {
  .history-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 8px;

    .history-count {
      font-size: 12px;
      color: #8c959f;
    }
  }

  .history-items {
    display: flex;
    flex-direction: column;
    gap: 8px;
    max-height: 520px;
    overflow-y: auto;
  }

  .history-item {
    position: relative;
    padding: 8px 10px;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    cursor: pointer;
    transition: border-color 0.2s, background 0.2s;

    &:hover {
      border-color: #93c5fd;
      background: #f8fafc;
    }

    .history-item-head {
      display: flex;
      align-items: center;
      gap: 6px;
      padding-right: 22px;
    }

    .history-query {
      flex: 1;
      min-width: 0;
      font-size: 13px;
      font-weight: 600;
      color: #1f2937;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .history-time {
      flex-shrink: 0;
      font-size: 11px;
      color: #9ca3af;
      font-variant-numeric: tabular-nums;
    }

    .history-preview {
      margin: 6px 0 0;
      font-size: 12px;
      line-height: 1.6;
      color: #6b7280;
    }

    .history-delete {
      position: absolute;
      top: 6px;
      right: 6px;
      width: 20px;
      height: 20px;
      display: flex;
      align-items: center;
      justify-content: center;
      border: none;
      border-radius: 4px;
      background: transparent;
      color: #c0c4cc;
      cursor: pointer;
      font-size: 12px;

      &:hover {
        background: #fde8e8;
        color: #ef4444;
      }
    }
  }
}
</style>
