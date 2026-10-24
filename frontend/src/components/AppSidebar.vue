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
  { to: '/', label: "Vue d'ensemble", icon: LayoutDashboard },
  { to: '/products', label: 'Produits', icon: PackageSearch },
  { to: '/recommendations', label: 'Recommandations', icon: Sparkles },
  { to: '/nlp', label: 'Laboratoire NLP', icon: BrainCircuit },
  { to: '/system', label: 'Pipeline & système', icon: Activity },
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
        <span>{{ item.label }}</span>
      </RouterLink>
    </nav>

    <div class="sidebar-status">
      <div class="status-line"><span class="status-dot" /> Système opérationnel</div>
      <p>1 million d'avis analysés par le pipeline NLP.</p>
    </div>
    <div class="sidebar-footer">Kafka · Spark · MongoDB</div>
  </aside>
</template>
