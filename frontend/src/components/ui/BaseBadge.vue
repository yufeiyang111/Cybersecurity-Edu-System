<template>
  <span class="ui-badge" :class="[`ui-badge--${type}`, { 'ui-badge--dot': dot }]">
    <span v-if="!dot" class="ui-badge__text">
      <slot />
    </span>
    <span v-if="dot" class="ui-badge__dot" :class="{ 'ui-badge__dot--pulse': pulse }" />
    <slot v-if="!dot && !$slots.default" name="after" />
  </span>
</template>

<script setup>
defineProps({
  type: {
    type: String,
    default: 'default',
    validator: (v) => ['default', 'blue', 'green', 'red', 'orange', 'yellow', 'gray'].includes(v),
  },
  dot: { type: Boolean, default: false },
  pulse: { type: Boolean, default: false },
})
</script>

<style scoped>
.ui-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  font-weight: 600;
  border-radius: 999px;
  line-height: 1;
  white-space: nowrap;
}

.ui-badge--default {
  background: #f1f5f9;
  color: #475569;
}

.ui-badge--blue {
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  color: #1d4ed8;
}

.ui-badge--green {
  background: #dcfce7;
  border: 1px solid #bbf7d0;
  color: #15803d;
}

.ui-badge--red {
  background: #fee2e2;
  border: 1px solid #fecaca;
  color: #b91c1c;
}

.ui-badge--orange {
  background: #ffedd5;
  border: 1px solid #fed7aa;
  color: #9a3412;
}

.ui-badge--yellow {
  background: #fef9c3;
  border: 1px solid #fde68a;
  color: #854d0e;
}

.ui-badge--gray {
  background: #f1f5f9;
  color: #475569;
}

.ui-badge__text {
  padding: 2px 8px;
}

.ui-badge__dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #15803d;
}

.ui-badge__dot--pulse {
  animation: badge-pulse 1.5s ease-in-out infinite;
}

@keyframes badge-pulse {
  0%,
  100% {
    opacity: 1;
  }

  50% {
    opacity: 0.3;
  }
}
</style>
