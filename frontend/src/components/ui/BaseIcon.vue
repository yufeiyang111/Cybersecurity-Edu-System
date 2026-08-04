<template>
  <svg
    class="ui-icon"
    :width="size"
    :height="size"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    :stroke-width="strokeWidth"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
    v-html="iconPath"
  />
</template>

<script setup>
import { computed } from 'vue'
import { ICONS } from './icons.js'

const props = defineProps({
  name: { type: String, required: true },
  size: { type: Number, default: 16 },
  strokeWidth: { type: Number, default: 2 },
})

const iconPath = computed(() => ICONS[props.name] ?? '')
</script>

<style scoped>
.ui-icon { display: inline-block; vertical-align: middle; flex-shrink: 0; }
</style>
