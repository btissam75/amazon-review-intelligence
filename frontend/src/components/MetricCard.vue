<script setup lang="ts">
import type { Component } from 'vue'

defineProps<{
  label: string
  value: string
  detail: string
  icon: Component
  tone?: 'cyan' | 'violet' | 'green' | 'amber'
}>()
</script>

<template>
  <article class="metric-card" :class="`tone-${tone || 'cyan'}`">
    <div class="metric-icon"><component :is="icon" :size="21" /></div>
    <div class="metric-copy">
      <span>{{ label }}</span>
      <strong>{{ value }}</strong>
      <small>{{ detail }}</small>
    </div>
  </article>
</template>
