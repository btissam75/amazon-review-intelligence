<script setup lang="ts">
import { ChevronLeft, ChevronRight, Search, SlidersHorizontal, X } from '@lucide/vue'
import { onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import { api, errorMessage } from '../api/client'
import PageHeader from '../components/PageHeader.vue'
import StateNotice from '../components/StateNotice.vue'
import type { ProductProfile, Review } from '../types'

const route = useRoute()
const products = ref<ProductProfile[]>([])
const search = ref('')
const minQuality = ref(0)
const offset = ref(0)
const limit = 20
const loading = ref(false)
const error = ref('')
const selected = ref<{ profile: ProductProfile; reviews: Review[] } | null>(null)
const detailLoading = ref(false)
const number = new Intl.NumberFormat('fr-FR')
let timer: number | undefined

async function loadProducts(reset = false) {
  if (reset) offset.value = 0
  loading.value = true
  error.value = ''
  try {
    const { data } = await api.get<{ items: ProductProfile[] }>('/api/v1/products', {
      params: {
        offset: offset.value,
        limit,
        search: search.value || undefined,
        min_quality: minQuality.value,
      },
    })
    products.value = data.items
  } catch (cause) {
    error.value = errorMessage(cause)
  } finally {
    loading.value = false
  }
}

async function openProduct(productId: string) {
  detailLoading.value = true
  error.value = ''
  try {
    const { data } = await api.get<{ profile: ProductProfile; reviews: Review[] }>(
      `/api/v1/products/${encodeURIComponent(productId)}`,
    )
    selected.value = data
  } catch (cause) {
    error.value = errorMessage(cause)
  } finally {
    detailLoading.value = false
  }
}

watch([search, minQuality], () => {
  window.clearTimeout(timer)
  timer = window.setTimeout(() => loadProducts(true), 350)
})

onMounted(async () => {
  await loadProducts()
  if (typeof route.query.product === 'string') openProduct(route.query.product)
})
</script>

<template>
  <div class="page-container">
    <PageHeader
      eyebrow="Catalogue intelligent"
      title="Produits analysés"
      description="Recherchez parmi 154 311 profils construits à partir des notes, sentiments et achats vérifiés."
    />

    <section class="filter-bar panel">
      <label class="search-field"><Search :size="18" /><input v-model="search" placeholder="Rechercher un identifiant produit…" /></label>
      <label class="quality-filter">
        <SlidersHorizontal :size="17" /><span>Qualité min. {{ Math.round(minQuality * 100) }}%</span>
        <input v-model.number="minQuality" type="range" min="0" max="0.9" step="0.05" />
      </label>
    </section>

    <StateNotice :loading="loading && !products.length" :message="error" />

    <section class="product-grid" :class="{ muted: loading }">
      <button v-for="product in products" :key="product.product_id" class="product-card" @click="openProduct(product.product_id)">
        <div class="product-card-top"><span class="product-avatar">{{ product.product_id.slice(0, 2).toUpperCase() }}</span><span class="score-chip">{{ Math.round(product.quality_score * 100) }} qualité</span></div>
        <div><h2>{{ product.product_id }}</h2><p>{{ number.format(product.review_count) }} avis analysés</p></div>
        <div class="product-stats"><span><strong>{{ product.average_rating.toFixed(1) }}</strong> / 5</span><span><strong>{{ Math.round(product.positive_ratio * 100) }}%</strong> positifs</span><span><strong>{{ Math.round(product.verified_ratio * 100) }}%</strong> vérifiés</span></div>
        <div class="progress-track"><i :style="{ width: `${product.quality_score * 100}%` }" /></div>
      </button>
    </section>

    <div class="pagination-row">
      <button class="secondary-button" :disabled="offset === 0 || loading" @click="offset = Math.max(0, offset - limit); loadProducts()"><ChevronLeft :size="17" /> Précédent</button>
      <span>Résultats {{ number.format(offset + 1) }}–{{ number.format(offset + products.length) }}</span>
      <button class="secondary-button" :disabled="products.length < limit || loading" @click="offset += limit; loadProducts()">Suivant <ChevronRight :size="17" /></button>
    </div>

    <div v-if="selected || detailLoading" class="drawer-layer" @click.self="selected = null">
      <aside class="detail-drawer">
        <button class="drawer-close" aria-label="Fermer" @click="selected = null"><X /></button>
        <div v-if="detailLoading" class="drawer-loader">Chargement du profil…</div>
        <template v-else-if="selected">
          <p class="eyebrow">Analyse produit</p><h2>{{ selected.profile.product_id }}</h2>
          <div class="detail-score"><strong>{{ Math.round(selected.profile.quality_score * 100) }}</strong><span>Score qualité<br/>NLP / 100</span></div>
          <div class="detail-metrics"><div><span>Note</span><strong>{{ selected.profile.average_rating.toFixed(2) }} ★</strong></div><div><span>Positif</span><strong>{{ Math.round(selected.profile.positive_ratio * 100) }}%</strong></div><div><span>Confiance</span><strong>{{ Math.round(selected.profile.average_confidence * 100) }}%</strong></div></div>
          <h3>Avis récents</h3>
          <div class="review-list">
            <article v-for="review in selected.reviews" :key="review.review_id" class="review-card">
              <div><span :class="`sentiment-badge ${review.sentiment_label}`">{{ review.sentiment_label }}</span><span>{{ review.rating }} ★</span></div>
              <strong v-if="review.title">{{ review.title }}</strong><p>{{ review.text }}</p>
              <small>Confiance {{ Math.round(review.sentiment_score * 100) }}%<template v-if="review.verified_purchase"> · Achat vérifié</template></small>
            </article>
          </div>
        </template>
      </aside>
    </div>
  </div>
</template>
