// Shared domain types used across the frontend (mirrors backend Pydantic schemas).

// Structured extra detail kept on mapped business rows (e.g. Google Maps
// rating / review count / native category). Extra unknown keys are tolerated.
export interface BusinessMetadata {
  rating?: number
  review_count?: number
  google_category?: string
  opening_hours_state?: string
}

export interface Business {
  id: string
  name: string
  category_code?: string
  subcategory?: string
  latitude: number
  longitude: number
  address?: string
  phone?: string
  website?: string
  opening_hours?: string
  brand?: string
  distance_km?: number
  source_name?: string
  source_type?: string
  confidence?: string
  confidence_score?: number
  verification_status?: string
  retrieved_at_date?: string
  is_demo?: boolean
  metadata?: BusinessMetadata
}

export interface InfrastructurePoint {
  id: string
  kind: string
  name?: string
  latitude: number
  longitude: number
  distance_km?: number
  source_name?: string
  source_type?: string
  confidence?: string
  is_demo?: boolean
}

export interface MapPoint {
  id?: string
  name?: string
  kind?: string
  latitude: number
  longitude: number
  distance_km?: number
  source_name?: string
  confidence?: string
  is_demo?: boolean
}

export interface MSMECluster {
  pincode: string
  total: number
  activity_codes: number
  latitude: number
  longitude: number
  distance_km?: number
  geo_resolution?: string
  units?: Array<{ name: string; address?: string; nic_code?: string }>
}

export interface MSMEClusterFeatureCollection {
  type: 'FeatureCollection'
  features: Array<{
    type: 'Feature'
    properties: MSMECluster & {
      geo_resolution?: string
    }
    geometry: { type: 'Point'; coordinates: [number, number] }
  }>
}

export interface MapLayersResponse {
  center: { latitude: number; longitude: number }
  radius_km: number
  layers: {
    businesses?: any
    infrastructure?: any
    markets?: any
  }
  counts: { businesses: number; infrastructure: number; markets: number }
  note?: string
}

export interface LocationOut {
  id: string
  state: string
  district: string
  block?: string
  village?: string
  latitude: number
  longitude: number
  geo_precision: string
  source_name?: string
  confidence?: string
  reference_year?: number
}

export interface GeocodeResult {
  name: string
  display_name: string
  latitude: number
  longitude: number
  provider: string
  confidence?: string
}

export interface Category {
  code: string
  name: string
}

export interface OpportunityScore {
  overall_score: number
  demand_score: number
  competition_score: number
  accessibility_score: number
  price_score: number
  financial_fit_score: number
  risk_score: number
  confidence_score: number
  confidence_label: string
  confidence_factors?: any
  component_breakdown?: any
  weights?: any
  label?: string
}

export interface FinancialPlan {
  capital_available: number
  project_cost: number
  loan_amount: number
  margin_pct: number
  scheme_code?: string
  scheme_name?: string
  scheme_decision?: string
  scheme_reason?: string
  max_loan?: number
  interest_rate?: number
  tenure_years?: number
  moratorium_months?: number
  moratorium_mode?: string
  emi?: number
  source_document?: string
  notes?: string[]
}

export interface Repayment {
  monthly_emi?: number
  coverage_ratio?: number
  health_label?: string
  disclaimer?: string
}

export interface ProfitModel {
  category_code: string
  label: string
  is_estimate: boolean
  inputs: Record<string, number>
  outputs: Record<string, number>
  notes?: string[]
}

export interface Recommendation {
  label: 'GO' | 'MODIFY' | 'AVOID'
  reason: string
}

export interface AnalysisResult {
  analysis_id?: string
  location: {
    id: string
    state: string
    district: string
    block?: string
    village?: string
    latitude: number
    longitude: number
    geo_precision: string
    proposed_latitude?: number | null
    proposed_longitude?: number | null
    uses_proposed_location?: boolean
    source?: any
  }
  population: any
  business_competition: {
    mapped_competitors_5km: number
    mapped_competitors_10km: number
    nearest_competitor_km?: number
    nearest_competitor?: string
    data_completeness: string
    note?: string
    businesses?: Business[]
  }
  market?: any
  infrastructure: any
  weather: any
  data_confidence?: any
  opportunity_score: OpportunityScore
  financial_plan: FinancialPlan
  repayment: Repayment
  profit_model: ProfitModel
  recommendation: Recommendation
  data_sources: any[]
}
