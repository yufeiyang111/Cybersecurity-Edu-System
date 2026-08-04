<template>
  <component
    :is="tag"
    class="ui-btn"
    :class="[`ui-btn--${variant}`, { 'ui-btn--block': block }]"
    v-bind="$attrs"
  >
    <slot />
  </component>
</template>

<script setup>
defineOptions({ inheritAttrs: false })

defineProps({
  variant: {
    type: String,
    default: 'default',
    validator: (v) => ['default', 'primary', 'ghost', 'danger'].includes(v),
  },
  block: { type: Boolean, default: false },
  tag: { type: String, default: 'button' },
})
</script>

<style scoped>
.ui-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 7px 14px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 500;
  border: 1px solid #e2e8f0;
  background: #fff;
  color: #475569;
  cursor: pointer;
  text-decoration: none;
  transition: background 0.15s, color 0.15s, border-color 0.15s, box-shadow 0.15s;
  white-space: nowrap;
  line-height: 1;
}
.ui-btn:hover { background: #f1f5f9; }
.ui-btn:active { background: #e2e8f0; }

.ui-btn--primary {
  background: #2563eb;
  border-color: #2563eb;
  color: #fff;
}
.ui-btn--primary:hover { background: #1d4ed8; border-color: #1d4ed8; }
.ui-btn--primary:active { background: #1e40af; }

.ui-btn--ghost {
  background: transparent;
  border-color: #e2e8f0;
  color: #475569;
}
.ui-btn--ghost:hover { background: #f1f5f9; }

.ui-btn--danger {
  background: #fff;
  border-color: #fca5a5;
  color: #dc2626;
}
.ui-btn--danger:hover { background: #fef2f2; border-color: #f87171; }

.ui-btn--block { width: 100%; }
</style>
