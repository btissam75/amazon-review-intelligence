<script setup lang="ts">
import {
  Activity,
  Boxes,
  BrainCircuit,
  LayoutDashboard,
  PackageSearch,
  Sparkles,
  X,
} from '@lucide/vue'
import { RouterLink } from 'vue-router'

defineProps<{ open: boolean }>()
defineEmits<{ close: [] }>()

const navigation = [
  { to: '/', label: "Vue d'ensemble", detail: 'Comprendre', step: '01', icon: LayoutDashboard },
  { to: '/products', label: 'Produits & avis', detail: 'Explorer', step: '02', icon: PackageSearch },
  { to: '/nlp', label: 'Analyse NLP', detail: 'Analyser', step: '03', icon: BrainCircuit },
  { to: '/recommendations', label: 'Recommandations', detail: 'Décider', step: '04', icon: Sparkles },
]
</script>

<template>
  <aside class="sidebar" :class="{ open }">
    <div class="brand-row">
      <div class="brand-mark"><Boxes :size="22" /></div>
      <div>
        <strong>ARI</strong>
        <span>Review Intelligence</span>
      </div>
      <button class="sidebar-close" aria-label="Fermer" @click="$emit('close')"><X /></button>
    </div>

    <nav class="nav-list" aria-label="Navigation principale">
      <RouterLink
        v-for="item in navigation"
        :key="item.to"
        :to="item.to"
        class="nav-link"
        @click="$emit('close')"
      >
        <component :is="item.icon" :size="19" />
        <span class="nav-copy"><strong>{{ item.label }}</strong><small>{{ item.step }} · {{ item.detail }}</small></span>
      </RouterLink>
    </nav>

    <RouterLink to="/system" class="nav-link technical-link" @click="$emit('close')">
      <Activity :size="19" />
      <span class="nav-copy"><strong>Pipeline & système</strong><small>Espace technique</small></span>
    </RouterLink>

    <div class="sidebar-status">
      <div class="status-line"><span class="status-dot" /> Système opérationnel</div>
      <p>1 million d'avis analysés par le pipeline NLP.</p>
    </div>
    <div class="sidebar-footer">Kafka · Spark · MongoDB</div>
  </aside>
</template>
