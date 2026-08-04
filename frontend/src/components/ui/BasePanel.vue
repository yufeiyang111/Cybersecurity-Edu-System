<template>
  <article class="ui-panel">
    <header v-if="$slots.header || title" class="ui-panel__header">
      <slot name="header">
        <div class="ui-panel__title-group">
          <h3 class="ui-panel__title">{{ title }}</h3>
          <p v-if="subtitle" class="ui-panel__subtitle">{{ subtitle }}</p>
        </div>
        <div v-if="$slots.actions" class="ui-panel__actions">
          <slot name="actions" />
        </div>
      </slot>
    </header>
    <div class="ui-panel__body" :class="{ 'ui-panel__body--scroll': scroll }">
      <slot />
    </div>
    <footer v-if="$slots.footer" class="ui-panel__footer">
      <slot name="footer" />
    </footer>
  </article>
</template>

<script setup>
defineProps({
  title: { type: String, default: '' },
  subtitle: { type: String, default: '' },
  scroll: { type: Boolean, default: false },
})
</script>

<style scoped>
.ui-panel {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  overflow: hidden;
}

.ui-panel__header {
  padding: 14px 18px;
  border-bottom: 1px solid #e2e8f0;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.ui-panel__title-group { flex: 1; min-width: 0; }

.ui-panel__title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: #0f172a;
  display: flex;
  align-items: center;
  gap: 8px;
}

.ui-panel__subtitle {
  margin: 3px 0 0;
  font-size: 12px;
  color: #94a3b8;
}

.ui-panel__actions { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }

.ui-panel__body { padding: 14px; }
.ui-panel__body--scroll { max-height: 400px; overflow-y: auto; }

.ui-panel__footer {
  padding: 12px 18px;
  border-top: 1px solid #e2e8f0;
}
</style>
