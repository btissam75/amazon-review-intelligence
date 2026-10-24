<script setup lang="ts">
import { BrainCircuit, Eraser, Send, ShieldCheck } from '@lucide/vue'
import { computed, ref } from 'vue'

import { api, errorMessage } from '../api/client'
import PageHeader from '../components/PageHeader.vue'

const text = ref('This product is excellent, reliable and easy to use. I highly recommend it!')
const loading = ref(false)
const error = ref('')
const result = ref<{ label: string; confidence: number } | null>(null)
const examples = [
  { label: 'Positif', text: 'This product is excellent, reliable and easy to use. I highly recommend it!' },
  { label: 'Neutre', text: 'The product arrived yesterday. It works as described and the size is correct.' },
  { label: 'Négatif', text: 'Very disappointing quality. It stopped working after two days and support was unhelpful.' },
]
const labelFr: Record<string, string> = { positive: 'Positif', neutral: 'Neutre', negative: 'Négatif' }
const resultLabel = computed(() => (result.value ? labelFr[result.value.label] || result.value.label : ''))

async function analyze() {
  if (!text.value.trim()) return
  loading.value = true
  error.value = ''
  result.value = null
  try {
    const response = await api.post<{ label: string; confidence: number }>(
      '/api/v1/sentiment/predict',
      { text: text.value },
    )
    result.value = response.data
  } catch (cause) {
    error.value = errorMessage(cause)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="page-container">
    <PageHeader
      eyebrow="Inférence en direct"
      title="Laboratoire NLP"
      description="Testez le modèle TF-IDF + régression logistique utilisé par Spark pour enrichir les avis."
    />

    <section class="nlp-layout">
      <article class="panel nlp-editor">
        <div class="panel-heading"><div><span>Texte à analyser</span><h2>Avis client</h2></div><span>{{ text.length }} / 10 000</span></div>
        <textarea v-model="text" maxlength="10000" placeholder="Saisissez un avis en anglais…" />
        <div class="editor-actions"><button class="ghost-button" @click="text = ''; result = null"><Eraser :size="17" /> Effacer</button><button class="primary-button" :disabled="loading || !text.trim()" @click="analyze"><Send :size="17" /> {{ loading ? 'Analyse…' : 'Analyser le sentiment' }}</button></div>
        <div class="example-list"><span>Exemples rapides</span><button v-for="example in examples" :key="example.label" @click="text = example.text; result = null">{{ example.label }}</button></div>
      </article>

      <article class="panel result-panel" :class="result?.label">
        <template v-if="result">
          <div class="result-orb"><BrainCircuit :size="30" /><i :style="{ '--confidence': `${result.confidence * 360}deg` }" /></div>
          <p>Sentiment détecté</p><h2>{{ resultLabel }}</h2>
          <div class="confidence-value"><strong>{{ Math.round(result.confidence * 100) }}%</strong><span>de confiance</span></div>
          <div class="confidence-track"><i :style="{ width: `${result.confidence * 100}%` }" /></div>
          <div class="model-note"><ShieldCheck :size="18" /><span>Prédiction générée par le même modèle que le pipeline Spark.</span></div>
        </template>
        <template v-else>
          <div class="empty-orb"><BrainCircuit :size="34" /></div><h2>Prêt pour l'analyse</h2><p>Le résultat et son niveau de confiance apparaîtront ici.</p>
          <span v-if="error" class="inline-error">{{ error }}</span>
        </template>
      </article>
    </section>

    <section class="explain-grid">
      <article><span>01</span><h3>Prétraitement</h3><p>Normalisation et vectorisation TF-IDF des unigrammes et bigrammes.</p></article>
      <article><span>02</span><h3>Classification</h3><p>Régression logistique pondérée sur trois classes de sentiment.</p></article>
      <article><span>03</span><h3>Confiance</h3><p>La probabilité de la classe dominante accompagne chaque prédiction.</p></article>
    </section>
  </div>
</template>
