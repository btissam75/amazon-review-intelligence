<script setup lang="ts">
import {
  BadgeCheck,
  Box,
  BrainCircuit,
  ChartNoAxesCombined,
  RefreshCw,
  Sparkles,
  Star,
  Users,
} from '@lucide/vue'
import { computed, defineAsyncComponent, onMounted } from 'vue'
import { RouterLink } from 'vue-router'

import MetricCard from '../components/MetricCard.vue'
import PageHeader from '../components/PageHeader.vue'
import StateNotice from '../components/StateNotice.vue'
import { useDashboardStore } from '../stores/dashboard'

const RatingChart = defineAsyncComponent(() => import('../components/RatingChart.vue'))
const SentimentChart = defineAsyncComponent(() => import('../components/SentimentChart.vue'))
const store = useDashboardStore()
const number = new Intl.NumberFormat('fr-FR')
const percent = new Intl.NumberFormat('fr-FR', { style: 'percent', maximumFractionDigits: 1 })
const recommendationCoverage = computed(() => {
  if (!store.overview?.reviews) return 0
  return store.overview.recommendation_users / store.overview.reviews
})
const strategyNames = {
  popularity: 'Popularité',
  nlp_quality: 'Qualité NLP',
  als: 'ALS',
  hybrid: 'Hybride ALS + NLP',
}
const metricPercent = (value: number) => percent.format(value)

onMounted(() => store.load())
</script>

<template>
  <div class="page-container">
    <PageHeader
      eyebrow="Centre de commande"
      title="Comprendre chaque avis. Recommander avec confiance."
      description="Une lecture unifiée du pipeline NLP, de la qualité produit et des recommandations personnalisées."
    >
      <button class="secondary-button" :disabled="store.loading" @click="store.load(true)">
        <RefreshCw :size="17" :class="{ spin: store.loading }" /> Actualiser
      </button>
    </PageHeader>

    <StateNotice :loading="store.loading && !store.overview" :message="store.error">
      <button class="primary-button" @click="store.load(true)">Réessayer</button>
    </StateNotice>

    <template v-if="store.overview">
      <section class="metric-grid">
        <MetricCard
          label="Avis analysés"
          :value="number.format(store.overview.reviews)"
          detail="Corpus entièrement enrichi"
          :icon="BrainCircuit"
          tone="cyan"
        />
        <MetricCard
          label="Produits profilés"
          :value="number.format(store.overview.products)"
          detail="Scores qualité NLP"
          :icon="Box"
          tone="violet"
        />
        <MetricCard
          label="Utilisateurs servis"
          :value="number.format(store.overview.recommendation_users)"
          detail="Top-10 personnalisé"
          :icon="Users"
          tone="green"
        />
        <MetricCard
          label="Modèle hybride"
          value="Prêt"
          :detail="store.overview.model.model_version"
          :icon="Sparkles"
          tone="amber"
        />
      </section>

      <section class="dashboard-grid">
        <article class="panel span-7">
          <div class="panel-heading">
            <div><span>Sentiment global</span><h2>Voix des clients</h2></div>
            <span class="live-pill"><i /> Temps réel</span>
          </div>
          <SentimentChart v-if="store.sentiments" :items="store.sentiments.items" />
          <div v-if="store.sentiments" class="sentiment-legend-grid">
            <div v-for="item in store.sentiments.items" :key="item.label">
              <span :class="`sentiment-dot ${item.label}`" />
              <strong>{{ item.percentage }}%</strong>
              <small>Confiance {{ percent.format(item.average_confidence) }}</small>
            </div>
          </div>
        </article>

        <article class="panel span-5">
          <div class="panel-heading">
            <div><span>Distribution</span><h2>Notes attribuées</h2></div>
            <Star :size="20" class="accent-icon" />
          </div>
          <RatingChart v-if="store.details" :ratings="store.details.ratings" />
          <div class="verified-strip" v-if="store.details">
            <BadgeCheck :size="21" />
            <div><strong>{{ store.details.verified.percentage }}%</strong><span>achats vérifiés</span></div>
          </div>
        </article>

        <article class="panel span-8">
          <div class="panel-heading">
            <div><span>Classement NLP</span><h2>Produits à forte confiance</h2></div>
            <RouterLink class="text-link" to="/products">Explorer tout →</RouterLink>
          </div>
          <div class="compact-table">
            <div class="table-row table-head">
              <span>Produit</span><span>Qualité</span><span>Note</span><span>Avis</span>
            </div>
            <RouterLink
              v-for="product in store.products.slice(0, 6)"
              :key="product.product_id"
              :to="`/products?product=${product.product_id}`"
              class="table-row"
            >
              <strong class="table-product-name">{{ product.name }}<small>{{ product.brand || product.category }}</small></strong>
              <span><i class="quality-bar"><b :style="{ width: `${product.quality_score * 100}%` }" /></i>{{ Math.round(product.quality_score * 100) }}%</span>
              <span>{{ product.average_rating.toFixed(1) }} ★</span>
              <span>{{ number.format(product.review_count) }}</span>
            </RouterLink>
          </div>
        </article>

        <article class="panel span-4 insight-panel">
          <div><span class="kicker">Couverture personnalisée</span><strong>{{ number.format(store.overview.recommendation_users) }}</strong><p>utilisateurs disposent de recommandations hybrides ALS + NLP.</p></div>
          <div class="coverage-orbit"><span>{{ percent.format(recommendationCoverage) }}</span><small>du corpus</small></div>
          <RouterLink class="primary-button full-button" to="/recommendations">Tester une recommandation</RouterLink>
        </article>

        <article class="panel span-12 evaluation-panel">
          <div class="panel-heading">
            <div><span>Validation temporelle sans fuite</span><h2>Qualité des recommandations</h2></div>
            <ChartNoAxesCombined :size="20" class="accent-icon" />
          </div>
          <template v-if="store.recommendationEvaluation">
            <div class="evaluation-meta">
              <span>{{ number.format(store.recommendationEvaluation.eligible_users) }} utilisateurs testés</span>
              <span>Top-{{ store.recommendationEvaluation.k }}</span>
              <span>{{ new Date(store.recommendationEvaluation.evaluated_at).toLocaleDateString('fr-FR') }}</span>
              <strong>Gagnant : {{ strategyNames[store.recommendationEvaluation.winner] }}</strong>
            </div>
            <div class="evaluation-table">
              <div class="evaluation-row evaluation-head">
                <span>Stratégie</span><span>Hit Rate</span><span>NDCG</span><span>MRR</span><span>Couverture</span><span>Diversité</span>
              </div>
              <div
                v-for="item in store.recommendationEvaluation.strategies"
                :key="item.strategy"
                class="evaluation-row"
                :class="{ winner: item.strategy === store.recommendationEvaluation.winner }"
              >
                <strong>{{ strategyNames[item.strategy] }}</strong>
                <span>{{ metricPercent(item.hit_rate_at_k) }}</span>
                <span>{{ metricPercent(item.ndcg_at_k) }}</span>
                <span>{{ metricPercent(item.mrr_at_k) }}</span>
                <span>{{ metricPercent(item.catalog_coverage) }}</span>
                <span>{{ metricPercent(item.category_diversity) }}</span>
              </div>
            </div>
            <p class="evaluation-note">La dernière interaction de chaque utilisateur est masquée. Tous les signaux ALS et NLP sont recalculés uniquement sur son historique antérieur.</p>
          </template>
          <div v-else class="evaluation-empty">
            <strong>Évaluation prête à être exécutée</strong>
            <p>Lancez le job Spark d’évaluation pour comparer Popularité, Qualité NLP, ALS et modèle hybride sur les mêmes utilisateurs.</p>
            <code>docker compose --profile evaluation run --rm recommender-evaluation</code>
          </div>
        </article>
      </section>
    </template>
  </div>
</template>
