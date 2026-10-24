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
  review_count: number
  average_rating: number
  positive_ratio: number
  negative_ratio: number
  verified_ratio: number
  average_confidence: number
  quality_score: number
}

export interface Review {
  review_id: string
  rating: number
  title?: string
  text: string
  sentiment_label: string
  sentiment_score: number
  verified_purchase?: boolean
  review_timestamp?: string
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
}

export interface RecommendationResult {
  personalized: boolean
  user_id: string
  model_version: string
  generated_at?: string
  recommendations: Recommendation[]
}

export interface Health {
  status: string
  mongodb: string
  recommendation_model: string
}
