<template>
  <div class="help-doc-list">
    <div v-if="loading" class="help-doc-list__loading">
      <div class="skeleton-block"></div>
      <div class="skeleton-block"></div>
      <div class="skeleton-block"></div>
    </div>
    <div v-else-if="tree.length === 0" class="help-doc-list__empty">
      还没有分类，点击右上角「新建分类」开始。
    </div>
    <div v-else class="help-doc-list__scroll">
      <div v-for="category in tree" :key="category.id" class="doc-group">
        <div class="doc-group__title">
          <span>{{ category.name }}</span>
          <el-dropdown trigger="click" @command="(cmd) => handleCategoryCommand(cmd, category)">
            <button type="button" class="doc-group__more" aria-label="分类操作">
              <BaseIcon name="more" :size="14" />
            </button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="edit">编辑分类</el-dropdown-item>
                <el-dropdown-item command="delete" divided>删除分类</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
        <div v-for="child in category.children || []" :key="child.id" class="doc-subgroup">
          <div class="doc-subgroup__title">{{ child.name }}</div>
          <button
            v-for="doc in child.documents"
            :key="doc.id"
            type="button"
            class="doc-item"
            :class="{ 'is-active': doc.id === activeDocumentId }"
            @click="$emit('select-document', doc)"
          >
            <span class="doc-item__title">{{ doc.title }}</span>
            <span class="doc-item__badges">
              <BaseBadge v-if="!doc.is_active" type="gray">停用</BaseBadge>
              <BaseBadge v-if="doc.is_active" type="blue">v{{ doc.version }}</BaseBadge>
            </span>
          </button>
        </div>
        <template v-if="!(category.children || []).length">
          <button
            v-for="doc in category.documents || []"
            :key="doc.id"
            type="button"
            class="doc-item"
            :class="{ 'is-active': doc.id === activeDocumentId }"
            @click="$emit('select-document', doc)"
          >
            <span class="doc-item__title">{{ doc.title }}</span>
            <span class="doc-item__badges">
              <BaseBadge v-if="!doc.is_active" type="gray">停用</BaseBadge>
              <BaseBadge v-if="doc.is_active" type="blue">v{{ doc.version }}</BaseBadge>
            </span>
          </button>
        </template>
        <button
          type="button"
          class="doc-add"
          @click="$emit('select-document', { category_id: category.id, is_active: true })"
        >
          + 新建文档
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { BaseIcon, BaseBadge } from '@/components/ui'

defineProps({
  tree: {
    type: Array,
    default: () => []
  },
  loading: {
    type: Boolean,
    default: false
  },
  activeDocumentId: {
    type: Number,
    default: null
  }
})

const emit = defineEmits(['select-document', 'delete-document', 'edit-category', 'delete-category'])

const handleCategoryCommand = (cmd, category) => {
  if (cmd === 'edit') {
    emit('edit-category', category)
  } else if (cmd === 'delete') {
    emit('delete-category', category)
  }
}
</script>

<style scoped lang="scss">
.help-doc-list {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  max-height: calc(100vh - 180px);
  overflow: hidden;
  display: flex;
  flex-direction: column;

  &__loading {
    padding: 16px;

    .skeleton-block {
      height: 14px;
      border-radius: 4px;
      background: #f1f5f9;
      margin-bottom: 12px;
    }
  }

  &__empty {
    padding: 40px 20px;
    text-align: center;
    color: #94a3b8;
    font-size: 13px;
  }

  &__scroll {
    overflow-y: auto;
    padding: 12px;
  }
}

.doc-group {
  margin-bottom: 16px;

  &__title {
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-size: 13px;
    font-weight: 600;
    color: #0f172a;
    padding: 6px 8px;
  }

  &__more {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 24px;
    height: 24px;
    border: none;
    background: none;
    border-radius: 4px;
    color: #94a3b8;
    cursor: pointer;

    &:hover {
      background: #f1f5f9;
      color: #475569;
    }
  }
}

.doc-subgroup {
  margin-bottom: 4px;

  &__title {
    font-size: 12px;
    color: #94a3b8;
    padding: 4px 8px;
  }
}

.doc-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  width: 100%;
  padding: 7px 8px;
  border: none;
  background: none;
  border-radius: 6px;
  cursor: pointer;
  text-align: left;

  &:hover {
    background: #f1f5f9;
  }

  &.is-active {
    background: #eff6ff;

    .doc-item__title {
      color: #2563eb;
      font-weight: 600;
    }
  }

  &__title {
    font-size: 13px;
    color: #475569;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  &__badges {
    display: flex;
    gap: 4px;
    flex-shrink: 0;
  }
}

.doc-add {
  width: 100%;
  padding: 6px 8px;
  border: 1px dashed #cbd5e1;
  background: none;
  border-radius: 6px;
  color: #64748b;
  font-size: 12.5px;
  cursor: pointer;
  margin-top: 4px;

  &:hover {
    border-color: #2563eb;
    color: #2563eb;
    background: #eff6ff;
  }
}
</style>