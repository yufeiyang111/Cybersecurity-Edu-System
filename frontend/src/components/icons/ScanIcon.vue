<template>
  <svg class="icon" :width="size" :height="size" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <path d="M4 7V5a2 2 0 0 1 2-2h2M17 3h2a2 2 0 0 1 2 2v2M21 17v2a2 2 0 0 1-2 2h-2M7 21H6a2 2 0 0 1-2-2v-2" />
    <path d="M8 12h8M12 8v8" />
  </svg>
</template>

<script setup>
defineProps({ size: { type: Number, default: 15 } })
</script>
