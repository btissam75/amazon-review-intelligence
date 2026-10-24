<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

const route = useRoute()
const steps = [
  { to: '/', label: 'Comprendre', detail: 'Vue globale' },
  { to: '/products', label: 'Explorer', detail: 'Produits & avis' },
  { to: '/nlp', label: 'Analyser', detail: 'Sentiment NLP' },
  { to: '/recommendations', label: 'Décider', detail: 'Suggestions utiles' },
]

const activeIndex = computed(() => {
  const index = steps.findIndex((step) =>
    step.to === '/' ? route.path === '/' : route.path.startsWith(step.to),
  )
  return Math.max(0, index)
})
</script>

<template>
  <div class="journey-shell" aria-label="Parcours d'analyse">
    <div class="journey-intro">
      <span>Parcours intelligent</span>
      <strong>Des avis à la décision</strong>
    </div>
    <nav class="journey-steps">
      <RouterLink
        v-for="(step, index) in steps"
        :key="step.to"
        :to="step.to"
        class="journey-step"
        :class="{ active: index === activeIndex, complete: index < activeIndex }"
      >
        <span>{{ index + 1 }}</span>
        <div><strong>{{ step.label }}</strong><small>{{ step.detail }}</small></div>
      </RouterLink>
    </nav>
  </div>
</template>
