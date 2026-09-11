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

// ── Category-aware Market Intelligence ──
export interface MarketIntelligencePrice {
  item: string
  unit?: string | null
  min?: number | null
  max?: number | null
  modal?: number | null
  market?: string | null
  mandi?: string | null
  reference_date?: string | null
  days_old?: number | null
  freshness?: string
  relevance?: string
  is_estimate?: boolean
  is_demo?: boolean
  source?: Record<string, unknown>
}

export interface MarketIntelligenceSource {
  source_name: string
  dataset_name?: string | null
  source_type?: string | null
  sample_date?: string | null
  items: number
  is_estimate?: boolean
  is_demo?: boolean
}

export interface MarketIntelligenceResponse {
  category_code: string
  state: string
  district: string
  radius_km: number
  max_age_days?: number | null
  as_of: string
  available: boolean
  availability_note?: string
  commodity_scope?: {
    has_specific_commodities: boolean
    relevant_commodities?: string[]
    note?: string
  }
  prices: MarketIntelligencePrice[]
  coverage: number
  fresh_share: number
  confidence: { score: number; label: string }
  source_hierarchy: MarketIntelligenceSource[]
  demand_context?: {
    population_baseline?: number | null
    households?: number | null
    demand_score?: number | null
    commercial_demand_signals?: Record<string, { count: number; radius_km: number }>
    market_accessibility?: {
      nearest_market_km?: number | null
      markets_within_20km?: number
    }
    confidence?: number
    available_population?: boolean
  } | null
  notes?: string[]
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
  own_contribution: number
  required_financing: number
  shortfall: number
  shortfall_reason?: string
  loan_amount: number
  scale?: string
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

export interface UnifiedFinancial {
  project_cost: number
  own_capital: number
  financing_required: number
  shortfall: number
  shortfall_reason?: string | null
  scheme: {
    code?: string | null
    name?: string | null
    interest_rate?: number | null
    tenure_years?: number | null
    moratorium_months?: number | null
    moratorium_mode?: string | null
    max_loan_allowed?: number | null
    source_document?: string | null
    reason?: string | null
  }
  loan_amount: number
  emi: number
  total_interest: number
  total_repayment: number
  monthly_revenue?: number | null
  cogs?: number | null
  gross_profit?: number | null
  gross_margin_pct?: number | null
  opex?: number | null
  operating_profit?: number | null
  cash_surplus?: number | null
  break_even_revenue?: number | null
  working_capital_requirement?: number | null
  repayment_health?: string | null
  repayment_coverage?: number | null
}

export interface CostBreakdown {
  category_code: string
  scale: string
  capital_expenditure: Array<{ name: string; amount: number }>
  working_capital: Array<{ name: string; amount: number }>
  infrastructure: Array<{ name: string; amount: number }>
  licensing_compliance: Array<{ name: string; amount: number }>
  contingency_pct: number
  contingency_amount: number
  total_project_cost: number
  notes?: string[]
  location_factor: number
}

export interface Viability {
  decision: 'GO' | 'MODIFY' | 'AVOID'
  reason: string
  top_positive_factors: string[]
  top_negative_factors: string[]
  recommended_actions: string[]
  confidence_label?: string
}

export interface BusinessSetupPlan {
  category_code: string
  scale: string
  model?: string | null
  model_name?: string | null
  location_factor: number
  items: Array<{
    name: string
    amount: number
    category: string
    required_level: 'REQUIRED' | 'RECOMMENDED' | 'OPTIONAL'
    notes?: string
  }>
  startup_cost: number
  initial_inventory: number
  working_capital: number
  contingency_amount: number
  total_initial_requirement: number
  lean_option?: {
    total: number
    financing_needed: number
    items: any[]
  } | null
  operating_targets?: any
  inventory_plan?: any
  sourcing_needs?: any
  kpis?: any[]
  planned_values?: any
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
  suggested_businesses?: SuggestedBusiness[]
  population: any
  business_competition: {
    mapped_competitors_5km: number
    mapped_competitors_10km: number
    nearest_competitor_km?: number
    nearest_competitor?: string
    data_completeness: string
    note?: string
    businesses?: Business[]
    live_discovery?: any
  }
  market?: any
  infrastructure: any
  weather: any
  soil?: any
  price?: any
  location_features?: any
  industry_context?: any
  data_confidence?: any
  opportunity_score: OpportunityScore
  financial_plan: FinancialPlan
  unified_financial: UnifiedFinancial
  cost_breakdown: CostBreakdown
  repayment: Repayment
  repayment_detail?: any
  profit_model: ProfitModel
  category_profile?: any
  weather_intelligence?: any
  seasonal_intelligence?: any
  product_recommendations?: any
  monthly_economics: {
    monthly_revenue: number
    cogs: number
    gross_profit: number
    gross_margin_pct: number
    opex: number
    operating_profit: number
    emi: number
    cash_surplus: number
    break_even_revenue: number
    customers_per_day?: number
    avg_transaction_value?: number
    operating_days?: number
    opex_pct?: number
    operating_margin_pct?: number
    cash_surplus_pct?: number
    break_even_state?: string
    notes?: string[]
  }
  business_setup_plan: BusinessSetupPlan
  business_setup_plan_version?: number
  business_setup_plan_id?: string
  viability: Viability
  constraints: {
    constraints: Array<{
      id: string
      level: 'high' | 'medium' | 'low'
      title: string
      why: string
      what_to_do: string[]
    }>
    has_high: boolean
  }
  working_capital: {
    startup_investment: number
    initial_inventory: number
    operating_reserve: number
    recurring_opex: number
    debt_service: number
    estimated_working_capital_requirement: number
    recommended_buffer: number
    buffer_months: number
  }
  location_suitability: {
    score: number
    label: string
    factors: string[]
  }
  scale_fit: {
    recommended_scale: string
    scales: Array<{ scale: string; total_cost: number; fit_score: number; reason: string }>
  }
  recommendation: Recommendation
  loan_explainer: any
  data_sources: any[]
}

// ── Multilingual NLP Advisory ──
// Mirrors the backend /advisory/* endpoints (app/api/advisory.py).

export interface AdvisoryParseOutput {
  raw_text?: string
  detected_language?: string
  language_name?: string
  location?: {
    state?: string | null
    district?: string | null
    block?: string | null
    village?: string | null
  }
  business_type?: string | null
  category_name?: string | null
  scale?: string | null
  project_cost?: number | null
  capital_available?: number | null
  annual_income?: number | null
  age?: number | null
  beneficiary_category?: string | null
  confidence?: Record<string, number>
  amounts?: Record<string, number>
  keywords?: string[]
  entities?: string[]
}

export interface AdvisorySchemeMatch {
  scheme_code: string
  scheme_name: string
  match_score: number
  status: string
  matching_reasons: string[]
  mismatch_reasons: string[]
  missing_information: string[]
  scheme_details?: Record<string, any>
}

export interface AdvisoryLoanStructure {
  scheme_code?: string | null
  scheme_name?: string | null
  total_project_cost: number
  beneficiary_contribution?: number
  beneficiary_contribution_pct?: number
  loan_amount: number
  max_loan_allowed?: number | null
  subsidy_amount?: number
  subsidy_pct?: number | null
  interest_rate?: number
  tenure_years?: number
  moratorium_months?: number
  monthly_emi_during_moratorium?: number
  monthly_emi_after_moratorium?: number
  total_repayment?: number
  total_interest?: number
  repayment_health?: any
  notes?: string[]
  is_assumed?: boolean
  assumed_fields?: string[]
  scheme_source?: string | null
  alternatives?: any[]
}

export interface AdvisoryFinancialStructure {
  beneficiary?: Record<string, any>
  cost_breakdown?: any
  loan_structure?: AdvisoryLoanStructure
  recommended_scheme?: string | null
  alternatives?: any[]
  disclaimer?: string
}

export interface SuggestedBusiness {
  business_type: string
  label: string
  scale: string
  total_project_cost: number
  capital_available: number
  shortfall: number
  estimated_monthly_profit: number
  competitors_5km?: number | null
  eligible_schemes: number
  scores: { affordability: number; profit: number; competition: number; scheme: number; overall: number }
  overall_score: number
  reasons: string[]
}

export interface AdvisoryReport {
  parsed_input?: AdvisoryParseOutput
  beneficiary_profile?: any
  scheme_eligibility?: AdvisorySchemeMatch[]
  financial_structure?: AdvisoryFinancialStructure
  profit_model?: any
  business_intelligence?: any
  suggested_businesses?: SuggestedBusiness[]
  risks?: any
  action_plan?: any
  key_documents?: any
  summary?: string
  disclaimer?: string
}
