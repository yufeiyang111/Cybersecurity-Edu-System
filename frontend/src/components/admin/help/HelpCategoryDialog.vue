<template>
  <el-dialog
    :model-value="modelValue"
    :title="editingCategory ? '编辑分类' : '新建分类'"
    width="min(440px, calc(100vw - 32px))"
    destroy-on-close
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <el-form label-position="top" @submit.prevent="handleSubmit">
      <el-form-item label="分类名称" required>
        <el-input v-model.trim="form.name" maxlength="80" placeholder="例如：快速入门" />
      </el-form-item>
      <el-form-item label="slug" required>
        <el-input v-model.trim="form.slug" maxlength="64" placeholder="例如：getting-started（仅字母数字 - _）" />
      </el-form-item>
      <el-form-item label="父分类">
        <el-select v-model="form.parent_id" clearable placeholder="无（顶层分类）" style="width: 100%">
          <el-option
            v-for="category in topLevelCategories"
            :key="category.id"
            :label="category.name"
            :value="category.id"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="描述">
        <el-input v-model.trim="form.description" maxlength="255" type="textarea" :rows="2" />
      </el-form-item>
      <el-form-item label="排序">
        <el-input-number v-model="form.sort_order" :min="0" />
      </el-form-item>
      <el-form-item label="启用">
        <el-switch v-model="form.is_active" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="$emit('update:modelValue', false)">取消</el-button>
      <el-button type="primary" @click="handleSubmit">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, reactive, watch } from 'vue'
import { ElMessage } from 'element-plus'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  },
  tree: {
    type: Array,
    default: () => []
  },
  editingCategory: {
    type: Object,
    default: null
  }
})

const emit = defineEmits(['update:modelValue', 'submit'])

const form = reactive({
  name: '',
  slug: '',
  parent_id: null,
  description: '',
  sort_order: 0,
  is_active: true
})

const topLevelCategories = computed(() => props.tree)

watch(
  () => props.editingCategory,
  (category) => {
    if (category) {
      form.name = category.name || ''
      form.slug = category.slug || ''
      form.parent_id = category.parent_id ?? null
      form.description = category.description || ''
      form.sort_order = category.sort_order || 0
      form.is_active = category.is_active ?? true
    } else {
      form.name = ''
      form.slug = ''
      form.parent_id = null
      form.description = ''
      form.sort_order = 0
      form.is_active = true
    }
  },
  { immediate: true }
)

const handleSubmit = () => {
  if (!form.name.trim()) {
    ElMessage.warning('请填写分类名称')
    return
  }
  if (!form.slug.trim()) {
    ElMessage.warning('请填写 slug')
    return
  }
  emit('submit', {
    name: form.name.trim(),
    slug: form.slug.trim().toLowerCase(),
    parent_id: form.parent_id,
    description: form.description.trim(),
    sort_order: form.sort_order,
    is_active: form.is_active
  })
}
</script>