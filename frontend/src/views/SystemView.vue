<script setup lang="ts">
import { Activity, AlertTriangle, BrainCircuit, CheckCircle2, Database, RadioTower, RefreshCw, ServerCog, ShieldCheck, Workflow } from '@lucide/vue'
import { computed, onMounted, ref } from 'vue'

import { api, errorMessage } from '../api/client'
import PageHeader from '../components/PageHeader.vue'
import type { Health, MonitoringSnapshot, Overview } from '../types'

const health = ref<Health | null>(null)
const overview = ref<Overview | null>(null)
const monitoring = ref<MonitoringSnapshot | null>(null)
const error = ref('')
const monitoringMessage = ref('')
const loading = ref(true)
const number = new Intl.NumberFormat('fr-FR')
const percent = (value: number) => `${(value * 100).toFixed(2)}%`
const score = (value: number) => value.toFixed(3)
const date = (value: string) => new Intl.DateTimeFormat('fr-FR', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
const steps = [
  { name: 'Kafka', detail: 'Ingestion événementielle', icon: RadioTower, state: 'Batch terminé' },
  { name: 'Spark', detail: 'Nettoyage & inférence NLP', icon: Workflow, state: '1M traités' },
  { name: 'MongoDB', detail: 'Stockage analytique', icon: Database, state: 'Connecté' },
  { name: 'ALS + NLP', detail: 'Moteur de recommandation', icon: BrainCircuit, state: 'Prêt' },
  { name: 'FastAPI', detail: 'Couche de service', icon: ServerCog, state: 'En ligne' },
]

const statusCopy = computed(() => {
  if (!monitoring.value) return { title: 'Audit à exécuter', detail: monitoringMessage.value, icon: RefreshCw }
  if (monitoring.value.status === 'critical') return { title: 'Intervention requise', detail: 'Un seuil critique est dépassé.', icon: AlertTriangle }
  if (monitoring.value.status === 'warning') return { title: 'Surveillance recommandée', detail: 'Au moins un indicateur nécessite une vérification.', icon: AlertTriangle }
  return { title: 'Données et NLP sous contrôle', detail: 'Aucun seuil opérationnel dépassé.', icon: ShieldCheck }
})

async function refresh() {
  loading.value = true
  error.value = ''
  monitoringMessage.value = ''
  const [healthResult, overviewResult, monitoringResult] = await Promise.allSettled([
    api.get<Health>('/health'),
    api.get<Overview>('/api/v1/analytics/overview'),
    api.get<MonitoringSnapshot>('/api/v1/monitoring/status'),
  ])
  if (healthResult.status === 'fulfilled') health.value = healthResult.value.data
  else error.value = errorMessage(healthResult.reason)
  if (overviewResult.status === 'fulfilled') overview.value = overviewResult.value.data
  else error.value ||= errorMessage(overviewResult.reason)
  if (monitoringResult.status === 'fulfilled') monitoring.value = monitoringResult.value.data
  else {
    monitoring.value = null
    monitoringMessage.value = 'Lancez le profil Docker monitoring pour produire le premier snapshot.'
  }
  loading.value = false
}

onMounted(refresh)
</script>

<template>
  <div class="page-container">
    <PageHeader eyebrow="Observabilité" title="Pipeline, qualité & dérive NLP" description="Contrôler la chaîne technique, le contrat des données et la stabilité du modèle sur des fenêtres temporelles comparables.">
      <button class="secondary-button" :disabled="loading" @click="refresh"><Activity :size="17" /> Actualiser</button>
    </PageHeader>

    <div v-if="error" class="inline-error">{{ error }}</div>
    <section class="system-hero panel">
      <div class="system-health"><span class="health-ring"><CheckCircle2 :size="32" /></span><div><p>État de la plateforme</p><h2>{{ health?.status === 'ok' ? 'Services opérationnels' : 'Vérification en cours' }}</h2><span>MongoDB {{ health?.mongodb || '…' }} · Modèle {{ health?.recommendation_model || '…' }}</span></div></div>
      <div class="system-kpis" v-if="overview"><div><strong>{{ number.format(overview.reviews) }}</strong><span>documents enrichis</span></div><div><strong>{{ number.format(overview.recommendation_users) }}</strong><span>profils recommandés</span></div><div><strong>v1</strong><span>API publique</span></div></div>
    </section>

    <section class="monitoring-hero panel" :class="monitoring?.status || 'pending'">
      <div class="monitoring-title"><span class="monitoring-status-icon"><component :is="statusCopy.icon" :size="27" /></span><div><p class="eyebrow">Garde-fou ML</p><h2>{{ statusCopy.title }}</h2><span>{{ statusCopy.detail }}</span></div></div>
      <div v-if="monitoring" class="monitoring-score"><strong>{{ monitoring.quality_score.toFixed(1) }}</strong><span>/ 100 qualité</span><small>Audit du {{ date(monitoring.generated_at) }}</small></div>
      <code v-else>docker compose --profile monitoring run --rm monitoring</code>
    </section>

    <template v-if="monitoring">
      <section class="monitoring-kpis">
        <article class="panel"><span>Erreurs critiques</span><strong>{{ number.format(monitoring.data_quality.critical_errors) }}</strong><small>{{ percent(monitoring.data_quality.critical_error_rate) }} du corpus</small></article>
        <article class="panel"><span>Contenu dupliqué</span><strong>{{ number.format(monitoring.data_quality.duplicate_content) }}</strong><small>{{ percent(monitoring.data_quality.duplicate_rate) }} du corpus</small></article>
        <article class="panel"><span>Faible confiance</span><strong>{{ percent(monitoring.data_quality.low_confidence_rate) }}</strong><small>confiance moyenne {{ percent(monitoring.data_quality.average_confidence) }}</small></article>
        <article class="panel"><span>Couverture aspects</span><strong>{{ percent(monitoring.data_quality.aspect_coverage) }}</strong><small>{{ number.format(monitoring.data_quality.aspect_enriched) }} avis expliqués</small></article>
      </section>

      <section class="monitoring-layout">
        <article class="panel drift-card">
          <div class="section-heading"><div><p class="eyebrow">Stabilité temporelle</p><h2>Dérive NLP sur {{ monitoring.drift.window_days }} jours</h2></div><span class="status-chip" :class="monitoring.status">{{ monitoring.status }}</span></div>
          <div class="drift-metrics">
            <div><span>Jensen–Shannon sentiments</span><strong>{{ score(monitoring.drift.sentiment_jsd) }}</strong><small>&lt; 0,03 attendu</small></div>
            <div><span>PSI de confiance</span><strong>{{ score(monitoring.drift.confidence_psi) }}</strong><small>&lt; 0,10 attendu</small></div>
            <div><span>Variation de confiance</span><strong>{{ monitoring.drift.confidence_delta >= 0 ? '+' : '' }}{{ percent(monitoring.drift.confidence_delta) }}</strong><small>récent vs référence</small></div>
          </div>
          <div class="window-comparison">
            <div><span>Référence</span><strong>{{ number.format(monitoring.drift.baseline.total) }} avis</strong><small>{{ date(monitoring.drift.baseline.start) }} → {{ date(monitoring.drift.baseline.end) }}</small></div>
            <div><span>Fenêtre récente</span><strong>{{ number.format(monitoring.drift.current.total) }} avis</strong><small>{{ date(monitoring.drift.current.start) }} → {{ date(monitoring.drift.current.end) }}</small></div>
          </div>
        </article>

        <article class="panel alert-card">
          <p class="eyebrow">Alertes actionnables</p><h2>Décisions de surveillance</h2>
          <div class="alert-list">
            <div v-for="alert in monitoring.alerts" :key="alert.code" class="monitoring-alert" :class="alert.level"><component :is="alert.level === 'info' ? CheckCircle2 : AlertTriangle" :size="19" /><div><strong>{{ alert.code.replaceAll('_', ' ') }}</strong><span>{{ alert.message }}</span></div></div>
          </div>
        </article>
      </section>
    </template>

    <section class="pipeline-flow">
      <article v-for="(step, index) in steps" :key="step.name" class="pipeline-node"><span class="node-index">0{{ index + 1 }}</span><div class="node-icon"><component :is="step.icon" :size="25" /></div><h2>{{ step.name }}</h2><p>{{ step.detail }}</p><span class="node-status"><i />{{ step.state }}</span></article>
    </section>

    <section class="system-grid">
      <article class="panel"><p class="eyebrow">Contrat de service</p><h2>API REST documentée</h2><p>Les routes d'analyse, produits, recommandations, NLP et monitoring sont décrites automatiquement par OpenAPI.</p><a class="primary-button inline-button" href="http://localhost:8000/docs" target="_blank">Ouvrir Swagger ↗</a></article>
      <article class="panel"><p class="eyebrow">Modèle actif</p><h2>{{ overview?.model.model_version || 'hybrid-als-nlp-v1' }}</h2><p>65% personnalisation ALS · 25% qualité NLP · 10% popularité, avec stratégie de démarrage à froid.</p><span class="ready-banner"><CheckCircle2 :size="18" /> Registre : {{ overview?.model.status || 'ready' }}</span></article>
    </section>
  </div>
</template>
