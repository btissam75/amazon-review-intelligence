import { defineStore } from 'pinia'
import { ref } from 'vue'

import { api, errorMessage } from '../api/client'
import type {
  AnalyticsDetails,
  Health,
  Overview,
  ProductProfile,
  RecommendationEvaluation,
  SentimentDistribution,
} from '../types'

export const useDashboardStore = defineStore('dashboard', () => {
  const overview = ref<Overview | null>(null)
  const sentiments = ref<SentimentDistribution | null>(null)
  const details = ref<AnalyticsDetails | null>(null)
  const products = ref<ProductProfile[]>([])
  const health = ref<Health | null>(null)
  const recommendationEvaluation = ref<RecommendationEvaluation | null>(null)
  const loading = ref(false)
  const error = ref('')
  const updatedAt = ref<Date | null>(null)

  async function load(force = false) {
    if (loading.value || (overview.value && !force)) return
    loading.value = true
    error.value = ''
    try {
      const [overviewResponse, sentimentResponse, detailResponse, productResponse, healthResponse] =
        await Promise.all([
          api.get<Overview>('/api/v1/analytics/overview'),
          api.get<SentimentDistribution>('/api/v1/analytics/sentiments'),
          api.get<AnalyticsDetails>('/api/v1/analytics/details'),
          api.get<{ items: ProductProfile[] }>('/api/v1/products', {
            params: { limit: 8, min_quality: 0.45 },
          }),
          api.get<Health>('/health'),
        ])
      overview.value = overviewResponse.data
      sentiments.value = sentimentResponse.data
      details.value = detailResponse.data
      products.value = productResponse.data.items
      health.value = healthResponse.data
      try {
        recommendationEvaluation.value = (
          await api.get<RecommendationEvaluation>('/api/v1/recommendations/evaluation')
        ).data
      } catch {
        recommendationEvaluation.value = null
      }
      updatedAt.value = new Date()
    } catch (cause) {
      error.value = errorMessage(cause)
    } finally {
      loading.value = false
    }
  }

  return {
    overview,
    sentiments,
    details,
    products,
    health,
    recommendationEvaluation,
    loading,
    error,
    updatedAt,
    load,
  }
})
