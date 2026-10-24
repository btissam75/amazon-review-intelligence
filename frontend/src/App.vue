<script setup lang="ts">
import { Menu, Moon, Sun } from '@lucide/vue'
import { onMounted, ref, watch } from 'vue'
import { RouterView } from 'vue-router'
import { useRoute } from 'vue-router'

import AppSidebar from './components/AppSidebar.vue'
import JourneyBar from './components/JourneyBar.vue'

const sidebarOpen = ref(false)
const dark = ref(localStorage.getItem('ari-theme') !== 'light')
const route = useRoute()

function applyTheme() {
  document.documentElement.dataset.theme = dark.value ? 'dark' : 'light'
  localStorage.setItem('ari-theme', dark.value ? 'dark' : 'light')
}

watch(dark, applyTheme)
onMounted(applyTheme)
</script>

<template>
  <div class="app-shell">
    <AppSidebar :open="sidebarOpen" @close="sidebarOpen = false" />
    <button
      v-if="sidebarOpen"
      class="sidebar-overlay"
      aria-label="Fermer le menu"
      @click="sidebarOpen = false"
    />
    <main class="main-shell">
      <header class="mobile-header">
        <button class="icon-button" aria-label="Ouvrir le menu" @click="sidebarOpen = true">
          <Menu :size="20" />
        </button>
        <span class="mobile-brand">ARI</span>
        <button class="icon-button" aria-label="Changer de thème" @click="dark = !dark">
          <Sun v-if="dark" :size="19" />
          <Moon v-else :size="19" />
        </button>
      </header>
      <button class="theme-toggle desktop-only" aria-label="Changer de thème" @click="dark = !dark">
        <Sun v-if="dark" :size="18" />
        <Moon v-else :size="18" />
      </button>
      <JourneyBar v-if="route.path !== '/system'" />
      <RouterView />
    </main>
  </div>
</template>
