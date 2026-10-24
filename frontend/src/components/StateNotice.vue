<script setup lang="ts">
import { AlertTriangle, LoaderCircle } from '@lucide/vue'

defineProps<{ loading?: boolean; message?: string }>()
</script>

<template>
  <div v-if="loading" class="state-notice">
    <LoaderCircle class="spin" :size="24" />
    <div><strong>Chargement des analyses</strong><span>MongoDB prépare les indicateurs.</span></div>
  </div>
  <div v-else-if="message" class="state-notice error-state">
    <AlertTriangle :size="24" />
    <div><strong>Impossible de charger les données</strong><span>{{ message }}</span></div>
    <slot />
  </div>
</template>
