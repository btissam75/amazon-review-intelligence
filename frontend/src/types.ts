export interface ModelStatus {
  model_version: string
  recommendation_documents: number
  status: string
  trained_at: string
}

export interface Overview {
  reviews: number
  products: number
  recommendation_users: number
  model: ModelStatus
}

export interface SentimentItem {
  label: 'positive' | 'negative' | 'neutral'
  total: number
  percentage: number
  average_confidence: number
}

export interface SentimentDistribution {
  total: number
  items: SentimentItem[]
}

export interface AnalyticsDetails {
  ratings: Array<{ rating: number; total: number }>
  verified: { total: number; verified: number; percentage: number }
  categories: Array<{ category: string; total: number }>
}

export interface ProductProfile {
  product_id: string
  name: string
  brand?: string
  price?: number
  image_url?: string
  category: string
  main_category?: string
  metadata_available?: boolean
  categories?: string[]
  features?: string[]
  description?: string[]
  review_count: number
  average_rating: number
  positive_ratio: number
  negative_ratio: number
  verified_ratio: number
  average_confidence: number
  quality_score: number
  review_highlight?: ReviewHighlight
}

export interface ReviewHighlight {
  category?: string
  title?: string
  text?: string
  rating?: number
  sentiment_label?: string
  sentiment_score?: number
  helpful_vote?: number
}

export interface Review {
  review_id: string
  rating: number
  title?: string
  text: string
  sentiment_label: string
  sentiment_score: number
  verified_purchase?: boolean
  helpful_vote?: number
  category?: string
  review_timestamp?: string
  aspect_sentiments?: AspectSentiment[]
  aspect_model_version?: string
}

export interface AspectSentiment {
  aspect: 'quality' | 'price' | 'delivery' | 'packaging' | 'durability' | 'usability'
  label: 'positive' | 'negative' | 'neutral'
  score: number
  mentions: number
  evidence: string[]
}

export interface AspectAnalyticsItem {
  aspect: AspectSentiment['aspect']
  reviews: number
  mentions: number
  distribution: Record<'negative' | 'neutral' | 'positive', number>
  positive_percentage: number
  negative_percentage: number
  average_confidence: number
}

export interface AspectAnalytics {
  model_version: string
  scope: { type?: string; product_id?: string }
  job?: {
    status: string
    target: number
    processed: number
    reviews_with_aspects?: number
  }
  items: AspectAnalyticsItem[]
}

export interface Recommendation {
  rank?: number
  product_id: string
  score?: number
  als_prediction?: number
  quality_score?: number
  positive_ratio?: number
  average_rating?: number
  review_count?: number
  reason?: string
  name?: string
  brand?: string
  image_url?: string
  category?: string
  metadata_available?: boolean
  review_highlight?: ReviewHighlight
}

export interface RecommendationResult {
  personalized: boolean
  user_id: string
  model_version: string
  generated_at?: string
  recommendations: Recommendation[]
}

export interface RecommendationStrategyMetrics {
  strategy: 'popularity' | 'nlp_quality' | 'als' | 'hybrid'
  users: number
  precision_at_k: number
  recall_at_k: number
  hit_rate_at_k: number
  ndcg_at_k: number
  mrr_at_k: number
  catalog_coverage: number
  category_diversity: number
  novelty_bits: number
}

export interface RecommendationEvaluation {
  model_version: string
  evaluated_at: string
  protocol: string
  leakage_control: string
  k: number
  eligible_users: number
  training_interactions: number
  training_products: number
  winner: RecommendationStrategyMetrics['strategy']
  strategies: RecommendationStrategyMetrics[]
}

export interface NlpClassMetrics {
  precision: number
  recall: number
  f1: number
  support: number
}

export interface NlpHumanEvaluation {
  model_name: string
  model_version: string
  evaluated_at: string
  evaluation_source: string
  dataset: {
    size: number
    human_distribution: Record<string, number>
    prediction_distribution: Record<string, number>
  }
  metrics: {
    accuracy: number
    macro_precision: number
    macro_recall: number
    macro_f1: number
    weighted_f1: number
  }
  per_class: Record<'negative' | 'neutral' | 'positive', NlpClassMetrics>
  confusion_matrix: {
    labels: Array<'negative' | 'neutral' | 'positive'>
    values: number[][]
  }
  confidence: {
    mean: number
    low_confidence_threshold: number
    low_confidence_count: number
    low_confidence_ratio: number
  }
  weak_label_human_agreement: number | null
  error_count: number
}

export interface Health {
  status: string
  mongodb: string
  recommendation_model: string
}

export type MonitoringLevel = 'healthy' | 'warning' | 'critical'

export interface MonitoringWindow {
  start: string
  end: string
  total: number
  sentiment_counts: Record<string, number>
  sentiment_distribution: Record<'negative' | 'neutral' | 'positive', number>
  average_confidence: number
  low_confidence_rate: number
  confidence_histogram: number[]
}

export interface MonitoringSnapshot {
  version: string
  generated_at: string
  status: MonitoringLevel
  quality_score: number
  data_quality: {
    total: number
    critical_errors: number
    critical_error_rate: number
    duplicate_content: number
    duplicate_rate: number
    low_confidence: number
    low_confidence_rate: number
    average_confidence: number
    aspect_enriched: number
    aspect_coverage: number
    empty_text: number
    invalid_rating: number
    invalid_sentiment: number
  }
  drift: {
    window_days: number
    baseline: MonitoringWindow
    current: MonitoringWindow
    sentiment_jsd: number
    confidence_psi: number
    confidence_delta: number
  }
  alerts: Array<{
    level: 'info' | 'warning' | 'critical'
    code: string
    message: string
  }>
}
