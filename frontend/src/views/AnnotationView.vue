<script setup lang="ts">
import { CheckCircle2, ClipboardCheck, Keyboard, Save, UserRound } from '@lucide/vue'
import { computed, onMounted, onUnmounted, ref } from 'vue'

import { api, errorMessage } from '../api/client'
import PageHeader from '../components/PageHeader.vue'
import StateNotice from '../components/StateNotice.vue'

type Label = 'negative' | 'neutral' | 'positive'
type Decision = Label | 'uncertain'
type AnnotationTask = {
  review_id: string
  title?: string
  text: string
  category?: string
  required_annotations: number
  annotations?: { label: Decision; notes?: string }[]
}
type Progress = {
  total: number
  completed: number
  pending: number
  completion_percentage: number
  conflicts: number
  double_annotated: number
  cohen_kappa?: number
  reviewed_by_annotator: number
}
type Reveal = {
  source_rating?: number
  weak_label?: Label
  model_confidence?: number
  agreement: boolean
  annotation_count: number
  required_annotations: number
}

const annotator = ref(localStorage.getItem('ari-annotator') || '')
const task = ref<AnnotationTask | null>(null)
const progress = ref<Progress | null>(null)
const reveal = ref<Reveal | null>(null)
const notes = ref('')
const loading = ref(false)
const error = ref('')
const adjudicating = ref(false)
const sessionStarted = ref(false)
const canStart = computed(() => annotator.value.trim().length >= 2)
const labels: { value: Decision; title: string; shortcut: string; detail: string }[] = [
  { value: 'negative', title: 'Négatif', shortcut: '1', detail: 'Insatisfaction ou critique dominante' },
  { value: 'neutral', title: 'Neutre', shortcut: '2', detail: 'Information factuelle ou opinion équilibrée' },
  { value: 'positive', title: 'Positif', shortcut: '3', detail: 'Satisfaction ou appréciation dominante' },
  { value: 'uncertain', title: 'Incertain', shortcut: '4', detail: 'Ambigu, ironique ou contexte insuffisant' },
]

function labelFr(label?: Decision) {
  return ({ negative: 'Négatif', neutral: 'Neutre', positive: 'Positif', uncertain: 'Incertain' } as Record<string, string>)[label || ''] || '—'
}

async function loadProgress() {
  const { data } = await api.get<Progress>('/api/v1/annotations/progress', {
    params: { annotator: annotator.value.trim() },
  })
  progress.value = data
}

async function loadNext() {
  loading.value = true
  error.value = ''
  reveal.value = null
  notes.value = ''
  try {
    const endpoint = adjudicating.value
      ? '/api/v1/annotations/conflicts/next'
      : '/api/v1/annotations/next'
    const { data } = await api.get<{ task: AnnotationTask | null }>(endpoint, {
      params: adjudicating.value ? undefined : { annotator: annotator.value.trim() },
    })
    task.value = data.task
    await loadProgress()
  } catch (cause) {
    error.value = errorMessage(cause)
  } finally {
    loading.value = false
  }
}

async function start() {
  if (!canStart.value) return
  sessionStarted.value = true
  localStorage.setItem('ari-annotator', annotator.value.trim())
  await loadNext()
}

async function submit(label: Decision) {
  if (!task.value || loading.value || reveal.value) return
  loading.value = true
  error.value = ''
  try {
    const endpoint = adjudicating.value
      ? `/api/v1/annotations/${encodeURIComponent(task.value.review_id)}/adjudicate`
      : `/api/v1/annotations/${encodeURIComponent(task.value.review_id)}`
    const identity = adjudicating.value ? { adjudicator: annotator.value.trim() } : { annotator: annotator.value.trim() }
    const { data } = await api.post<Reveal>(endpoint, {
      ...identity,
      label,
      notes: notes.value.trim() || null,
    })
    reveal.value = data
    await loadProgress()
  } catch (cause) {
    error.value = errorMessage(cause)
  } finally {
    loading.value = false
  }
}

async function switchMode(mode: 'annotation' | 'adjudication') {
  adjudicating.value = mode === 'adjudication'
  await loadNext()
}

function onKeydown(event: KeyboardEvent) {
  const target = event.target as HTMLElement
  if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA') return
  const selected = labels.find((item) => item.shortcut === event.key)
  if (selected) submit(selected.value)
}

onMounted(() => {
  window.addEventListener('keydown', onKeydown)
  if (canStart.value) start()
})
onUnmounted(() => window.removeEventListener('keydown', onKeydown))
</script>

<template>
  <div class="page-container annotation-page">
    <PageHeader
      eyebrow="Qualité scientifique"
      title="Construire le corpus de référence"
      description="Annotez le texte sans voir la note Amazon ni la prédiction du modèle. Ces décisions humaines permettront une évaluation NLP réellement indépendante."
    />

    <section v-if="!sessionStarted || !task" class="annotation-start panel">
      <div class="annotation-start-icon"><ClipboardCheck :size="34" /></div>
      <template v-if="!sessionStarted">
        <h2>Identifiez votre session d'annotation</h2>
        <p>Utilisez un nom stable. Il sert uniquement à mesurer l'accord entre évaluateurs.</p>
        <form @submit.prevent="start">
          <label class="search-field"><UserRound :size="18" /><input v-model="annotator" minlength="2" maxlength="80" required placeholder="Nom ou pseudonyme de l'annotateur" /></label>
          <button class="primary-button"><ClipboardCheck :size="17" /> Commencer</button>
        </form>
      </template>
      <template v-else-if="progress?.total === 0">
        <h2>Aucun échantillon préparé</h2>
        <p>Initialisez d'abord les tâches équilibrées depuis le corpus MongoDB.</p>
        <code>docker compose run --rm api python -m amazon_review_intelligence.annotation.bootstrap</code>
      </template>
      <template v-else-if="!loading">
        <CheckCircle2 :size="38" class="annotation-complete" />
        <h2>Votre session est terminée</h2>
        <p>Merci — toutes les tâches disponibles pour {{ annotator }} ont été examinées.</p>
      </template>
    </section>

    <template v-if="task">
      <section v-if="progress" class="annotation-progress panel">
        <div><span>Progression globale</span><strong>{{ progress.completed }} / {{ progress.total }}</strong></div>
        <div class="annotation-progress-track"><i :style="{ width: `${progress.completion_percentage}%` }" /></div>
        <div class="annotation-progress-meta"><span>{{ progress.completion_percentage }}% validé</span><span>{{ progress.reviewed_by_annotator }} par {{ annotator }}</span><span v-if="progress.cohen_kappa != null">κ {{ progress.cohen_kappa }}</span><button v-if="progress.conflicts" class="text-link annotation-mode" @click="switchMode(adjudicating ? 'annotation' : 'adjudication')">{{ adjudicating ? 'Revenir à l’annotation' : `Arbitrer ${progress.conflicts} conflit(s)` }}</button></div>
      </section>

      <StateNotice :loading="loading && !reveal" :message="error" />

      <section class="annotation-workspace panel">
        <div class="annotation-context">
          <span>{{ task.category || 'Avis Amazon' }}</span>
          <span v-if="adjudicating">Arbitrage expert</span><span v-else-if="task.required_annotations === 2">Double annotation</span>
        </div>
        <h2 v-if="task.title">{{ task.title }}</h2>
        <blockquote>{{ task.text }}</blockquote>
        <p class="annotation-rule">Décidez uniquement à partir du texte. La note et la prédiction sont volontairement masquées.</p>

        <div v-if="adjudicating && task.annotations?.length" class="conflict-opinions">
          <article v-for="(annotation, index) in task.annotations" :key="index"><span>Décision {{ index + 1 }}</span><strong>{{ labelFr(annotation.label) }}</strong><small v-if="annotation.notes">{{ annotation.notes }}</small></article>
        </div>

        <textarea v-model="notes" maxlength="500" placeholder="Note optionnelle : ambiguïté, ironie, contexte manquant…" />

        <div v-if="!reveal" class="annotation-labels">
          <button v-for="item in labels" :key="item.value" :class="`annotation-label ${item.value}`" :disabled="loading" @click="submit(item.value)">
            <span>{{ item.shortcut }}</span><strong>{{ item.title }}</strong><small>{{ item.detail }}</small>
          </button>
        </div>

        <div v-else class="annotation-reveal">
          <div><span>Note dévoilée</span><strong>{{ reveal.source_rating ?? '—' }} ★</strong></div>
          <div><span>Label faible</span><strong>{{ labelFr(reveal.weak_label) }}</strong></div>
          <div><span>Confiance modèle</span><strong>{{ reveal.model_confidence != null ? `${Math.round(reveal.model_confidence * 100)}%` : '—' }}</strong></div>
          <button class="primary-button" @click="loadNext"><Save :size="17" /> Annotation suivante</button>
        </div>
      </section>

      <div class="annotation-shortcuts"><Keyboard :size="16" /> Raccourcis : 1 négatif · 2 neutre · 3 positif · 4 incertain</div>
    </template>
  </div>
</template>
