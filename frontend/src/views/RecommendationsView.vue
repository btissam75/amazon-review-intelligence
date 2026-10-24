<script setup lang="ts">
import { ArrowRight, CheckCircle2, Search, Sparkles, UserRound } from '@lucide/vue'
import { onMounted, ref } from 'vue'

import { api, errorMessage } from '../api/client'
import PageHeader from '../components/PageHeader.vue'
import StateNotice from '../components/StateNotice.vue'
import type { RecommendationResult } from '../types'

const samples = ref<string[]>([])
const userId = ref('')
const result = ref<RecommendationResult | null>(null)
const loading = ref(false)
const error = ref('')
const number = new Intl.NumberFormat('fr-FR')

function preferenceScore(value?: number) {
  if (value == null) return 0
  return Math.round(Math.max(0, Math.min(1, (value - 1) / 4)) * 100)
}

async function loadRecommendations(value = userId.value) {
  if (!value.trim()) return
  userId.value = value
  loading.value = true
  error.value = ''
  result.value = null
  try {
    const { data } = await api.get<RecommendationResult>(
      `/api/v1/recommendations/${encodeURIComponent(value.trim())}`,
    )
    result.value = data
  } catch (cause) {
    error.value = errorMessage(cause)
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  try {
    const { data } = await api.get<{ items: string[] }>('/api/v1/users/sample')
    samples.value = data.items
    if (samples.value[0]) loadRecommendations(samples.value[0])
  } catch (cause) {
    error.value = errorMessage(cause)
  }
})
</script>

<template>
  <div class="page-container">
    <PageHeader
      eyebrow="Moteur hybride ALS + NLP"
      title="Recommandations personnalisées"
      description="Explorez un Top-10 combinant préférences utilisateur, qualité des sentiments et popularité produit."
    />

    <section class="recommendation-search panel">
      <div><UserRound :size="22" /><div><strong>Choisissez un profil client</strong><span>Aucun identifiant technique n'est nécessaire pour tester l'expérience.</span></div></div>
      <div v-if="samples.length" class="sample-users profile-choices"><span>Profils de démonstration</span><button v-for="(sample, index) in samples" :key="sample" :class="{ active: sample === userId }" @click="loadRecommendations(sample)">Profil {{ index + 1 }}</button></div>
      <details class="advanced-id">
        <summary>Utiliser un identifiant utilisateur précis</summary>
        <form @submit.prevent="loadRecommendations()">
          <label class="search-field"><Search :size="18" /><input v-model="userId" required placeholder="Identifiant utilisateur…" /></label>
          <button class="primary-button" :disabled="loading"><Sparkles :size="17" /> Recommander</button>
        </form>
      </details>
    </section>

    <StateNotice :loading="loading" :message="error" />

    <template v-if="result && !loading">
      <div class="result-summary">
        <div><CheckCircle2 :size="20" /><span>{{ result.personalized ? 'Profil personnalisé' : 'Sélection de démarrage' }}</span></div>
        <span>{{ result.model_version }}</span>
      </div>
      <section class="recommendation-grid">
        <article v-for="(item, index) in result.recommendations" :key="item.product_id" class="recommendation-card">
          <span class="rank-number">#{{ item.rank || index + 1 }}</span>
          <img v-if="item.image_url" :src="item.image_url" :alt="item.name || 'Produit recommandé'" class="recommendation-image" loading="lazy" />
          <div v-else class="recommendation-icon">{{ (item.category || 'Produit').slice(0, 2).toUpperCase() }}</div>
          <div class="recommendation-main">
            <span>{{ item.brand || item.category || 'Sélection personnalisée' }}</span>
            <h2>{{ item.name || 'Produit recommandé' }}</h2>
            <small>Référence {{ item.product_id }}</small>
            <p>{{ item.reason || 'Produit populaire à forte qualité client' }}</p>
          </div>
          <div class="recommendation-score"><strong>{{ Math.round((item.score ?? item.quality_score ?? 0) * 100) }}</strong><span>score</span></div>
          <div class="recommendation-meta"><span v-if="item.average_rating">{{ item.average_rating.toFixed(1) }} ★</span><span v-if="item.positive_ratio">{{ Math.round(item.positive_ratio * 100) }}% positifs</span><span v-if="item.review_count">{{ number.format(item.review_count) }} avis</span></div>
          <blockquote v-if="item.review_highlight?.text" class="recommendation-comment">“{{ item.review_highlight.text.slice(0, 170) }}{{ item.review_highlight.text.length > 170 ? '…' : '' }}”</blockquote>
          <div class="score-explanation">
            <span><i :style="{ width: `${preferenceScore(item.als_prediction)}%` }" />Affinité {{ preferenceScore(item.als_prediction) }}%</span>
            <span><i :style="{ width: `${Math.round((item.quality_score || 0) * 100)}%` }" />Qualité NLP {{ Math.round((item.quality_score || 0) * 100) }}%</span>
          </div>
          <RouterLink :to="`/products?product=${item.product_id}`" class="card-link">Voir l'analyse <ArrowRight :size="15" /></RouterLink>
        </article>
      </section>
    </template>
  </div>
</template>
