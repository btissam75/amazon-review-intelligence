<script setup lang="ts">
import { Activity, BrainCircuit, CheckCircle2, Database, RadioTower, ServerCog, Workflow } from '@lucide/vue'
import { onMounted, ref } from 'vue'

import { api, errorMessage } from '../api/client'
import PageHeader from '../components/PageHeader.vue'
import type { Health, Overview } from '../types'

const health = ref<Health | null>(null)
const overview = ref<Overview | null>(null)
const error = ref('')
const loading = ref(true)
const number = new Intl.NumberFormat('fr-FR')
const steps = [
  { name: 'Kafka', detail: 'Ingestion événementielle', icon: RadioTower, state: 'Batch terminé' },
  { name: 'Spark', detail: 'Nettoyage & inférence NLP', icon: Workflow, state: '1M traités' },
  { name: 'MongoDB', detail: 'Stockage analytique', icon: Database, state: 'Connecté' },
  { name: 'ALS + NLP', detail: 'Moteur de recommandation', icon: BrainCircuit, state: 'Prêt' },
  { name: 'FastAPI', detail: 'Couche de service', icon: ServerCog, state: 'En ligne' },
]

async function refresh() {
  loading.value = true
  error.value = ''
  try {
    const [healthResponse, overviewResponse] = await Promise.all([
      api.get<Health>('/health'),
      api.get<Overview>('/api/v1/analytics/overview'),
    ])
    health.value = healthResponse.data
    overview.value = overviewResponse.data
  } catch (cause) {
    error.value = errorMessage(cause)
  } finally {
    loading.value = false
  }
}

onMounted(refresh)
</script>

<template>
  <div class="page-container">
    <PageHeader eyebrow="Observabilité" title="Pipeline & système" description="Une vue claire de la chaîne de valeur, de l'événement brut jusqu'à la recommandation servie.">
      <button class="secondary-button" :disabled="loading" @click="refresh"><Activity :size="17" /> Vérifier</button>
    </PageHeader>

    <div v-if="error" class="inline-error">{{ error }}</div>
    <section class="system-hero panel">
      <div class="system-health"><span class="health-ring"><CheckCircle2 :size="32" /></span><div><p>État global</p><h2>{{ health?.status === 'ok' ? 'Tous les systèmes sont opérationnels' : 'Vérification en cours' }}</h2><span>MongoDB {{ health?.mongodb || '…' }} · Modèle {{ health?.recommendation_model || '…' }}</span></div></div>
      <div class="system-kpis" v-if="overview"><div><strong>{{ number.format(overview.reviews) }}</strong><span>documents enrichis</span></div><div><strong>{{ number.format(overview.recommendation_users) }}</strong><span>profils recommandés</span></div><div><strong>v1</strong><span>API publique</span></div></div>
    </section>

    <section class="pipeline-flow">
      <article v-for="(step, index) in steps" :key="step.name" class="pipeline-node">
        <span class="node-index">0{{ index + 1 }}</span><div class="node-icon"><component :is="step.icon" :size="25" /></div><h2>{{ step.name }}</h2><p>{{ step.detail }}</p><span class="node-status"><i />{{ step.state }}</span>
      </article>
    </section>

    <section class="system-grid">
      <article class="panel"><p class="eyebrow">Contrat de service</p><h2>API REST documentée</h2><p>Les routes d'analyse, produits, recommandations et NLP sont décrites automatiquement par OpenAPI.</p><a class="primary-button inline-button" href="http://localhost:8000/docs" target="_blank">Ouvrir Swagger ↗</a></article>
      <article class="panel"><p class="eyebrow">Modèle actif</p><h2>{{ overview?.model.model_version || 'hybrid-als-nlp-v1' }}</h2><p>65% personnalisation ALS · 25% qualité NLP · 10% popularité, avec stratégie de démarrage à froid.</p><span class="ready-banner"><CheckCircle2 :size="18" /> Registre : {{ overview?.model.status || 'ready' }}</span></article>
    </section>
  </div>
</template>
