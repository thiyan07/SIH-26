import { useState } from 'react'
import type { Business, InfrastructurePoint, MapPoint, MSMECluster } from '../types'
import { businessesToGeoJSON, infrastructureToGeoJSON, pointsToGeoJSON } from '../lib/geo'
import {
  Map,
  MapControls,
  MapGeoJSON,
  MapMarker,
  MapClusterLayer,
  createRadiusGeoJSON,
} from '../mapcn'

export interface BusinessMapProps {
  center: { latitude: number; longitude: number }
  businesses?: Business[]
  competitors?: Business[]
  markets?: MapPoint[]
  infrastructure?: InfrastructurePoint[]
  msmeClusters?: MSMECluster[]
  showRadius?: boolean
  zoom?: number
  height?: string
  selectedCategory?: string
}

// Category-specific competitor mapping: for each business type, which category_codes
// count as direct competitors on the map. This mirrors the backend's _competitors()
// in category_profiles.py so the frontend shows only relevant competitors.
const CATEGORY_COMPETITOR_MAP: Record<string, string[]> = {
  dairy: ['dairy'],
  poultry: ['poultry'],
  grocery: ['grocery'],
  textile: ['textile'],
  food_processing: ['food_processing'],
  restaurant: ['restaurant', 'food_processing', 'fast_food', 'tea_shop', 'bakery'],
  tea_shop: ['tea_shop', 'restaurant', 'bakery'],
  bakery: ['bakery', 'grocery', 'tea_shop'],
  clothing: ['clothing', 'textile', 'tailoring'],
  electronics: ['electronics', 'mobile_shop'],
  mobile_shop: ['mobile_shop', 'electronics'],
  furniture: ['furniture', 'electronics'],
  stationery: ['stationery', 'printing'],
  fertilizer: ['fertilizer', 'seed_shop'],
  seed_shop: ['seed_shop', 'fertilizer'],
  agricultural_equipment: ['agricultural_equipment', 'fertilizer'],
  animal_feed: ['animal_feed', 'fertilizer'],
  tractor_dealer: ['tractor_dealer', 'agricultural_equipment'],
  irrigation_supplies: ['irrigation_supplies', 'tractor_dealer'],
  mechanic: ['mechanic', 'tyre_shop', 'car_service'],
  tyre_shop: ['tyre_shop', 'mechanic'],
  car_service: ['car_service', 'mechanic', 'tyre_shop'],
  auto_parts: ['auto_parts', 'mechanic', 'tyre_shop'],
  salon: ['salon', 'tailoring'],
  tailoring: ['tailoring', 'clothing', 'textile'],
  printing: ['printing', 'stationery', 'computer_service'],
  computer_service: ['computer_service', 'electronics', 'mobile_shop'],
  laundry: ['laundry'],
  photography: ['photography', 'printing'],
  internet_centre: ['internet_centre', 'printing', 'computer_service'],
  travel_agency: ['travel_agency'],
  finance: ['finance'],
  welding: ['welding', 'hardware'],
  home_appliances: ['home_appliances', 'electronics'],
  battery_shop: ['battery_shop', 'mechanic'],
  pharmacy: ['pharmacy', 'clinic', 'diagnostic'],
  clinic: ['clinic', 'pharmacy', 'diagnostic'],
  hospital: ['hospital', 'clinic'],
  diagnostic: ['diagnostic', 'clinic', 'pharmacy'],
  dental_clinic: ['dental_clinic', 'clinic'],
  optical_shop: ['optical_shop', 'clinic'],
  veterinary: ['veterinary', 'animal_feed'],
  fruit_shop: ['fruit_shop', 'grocery', 'vegetable_shop'],
  vegetable_shop: ['vegetable_shop', 'grocery', 'fruit_shop'],
  sweet_shop: ['sweet_shop', 'bakery', 'restaurant'],
  hotel: ['hotel', 'restaurant'],
  fast_food: ['fast_food', 'restaurant', 'tea_shop'],
  fish_shop: ['fish_shop', 'grocery'],
  hardware: ['hardware', 'building_materials'],
  building_materials: ['building_materials', 'hardware'],
  steel_products: ['steel_products', 'building_materials', 'hardware'],
  plywood: ['plywood', 'hardware', 'building_materials'],
  agriculture: ['agriculture', 'fertilizer'],
  manufacturing: ['manufacturing'],
  handicrafts: ['handicrafts', 'textile'],
  meat_shop: ['meat_shop', 'grocery'],
}

// Fallback: broad competitor categories when no specific category is selected
export const COMPETITOR_CATEGORIES = new Set([
  'textile', 'grocery', 'restaurant', 'food_processing', 'dairy',
  'electronics', 'pharmacy', 'finance', 'clinic', 'dental_clinic',
  'bakery', 'tea_shop', 'fast_food', 'clothing', 'mobile_shop',
  'furniture', 'hardware', 'salon', 'tailoring', 'printing',
  'mechanic', 'tyre_shop', 'hospital', 'optical_shop', 'veterinary',
  'fruit_shop', 'vegetable_shop', 'sweet_shop', 'hotel', 'fish_shop',
  'meat_shop', 'building_materials', 'fertilizer', 'seed_shop',
])

const layerOptions = [
  { key: 'all', label: 'All' },
  { key: 'competitors', label: 'Competitors' },
  { key: 'markets', label: 'Markets' },
  { key: 'restaurants', label: 'Restaurants' },
  { key: 'retail', label: 'Retail' },
  { key: 'infrastructure', label: 'Infrastructure' },
  { key: 'msme', label: 'MSMEs' },
]

// Color palette for different category groups
const CATEGORY_COLORS: Record<string, string> = {
  restaurant: '#dc2626', food_processing: '#ef4444', fast_food: '#f87171',
  tea_shop: '#fb923c', bakery: '#f59e0b', grocery: '#16a34a',
  dairy: '#22c55e', textile: '#8b5cf6', clothing: '#a855f7',
  electronics: '#3b82f6', mobile_shop: '#60a5fa', pharmacy: '#06b6d4',
  hardware: '#78716c', salon: '#ec4899', tailoring: '#d946ef',
  printing: '#6366f1', mechanic: '#64748b', fertilizer: '#65a30d',
  seed_shop: '#84cc16', agricultural_equipment: '#4d7c0f',
  animal_feed: '#a3e635', tractor_dealer: '#14b8a6',
  welding: '#f97316', home_appliances: '#8b5cf6',
  furniture: '#a78bfa', stationery: '#60a5fa',
  fruit_shop: '#22c55e', vegetable_shop: '#16a34a',
  sweet_shop: '#fbbf24', hotel: '#f59e0b',
  meat_shop: '#dc2626', building_materials: '#78716c',
  fish_shop: '#06b6d4', optical_shop: '#818cf8',
  camera_shop: '#a78bfa', battery_shop: '#64748b',
}

// Group categories for the legend
const LEGEND_GROUPS = [
  { label: 'Food', color: '#dc2626', categories: ['restaurant', 'fast_food', 'food_processing', 'bakery', 'tea_shop', 'sweet_shop'] },
  { label: 'Groceries', color: '#16a34a', categories: ['grocery', 'dairy', 'fruit_shop', 'vegetable_shop', 'meat_shop', 'fish_shop'] },
  { label: 'Textile', color: '#8b5cf6', categories: ['textile', 'clothing', 'tailoring'] },
  { label: 'Electronics', color: '#3b82f6', categories: ['electronics', 'mobile_shop', 'home_appliances', 'furniture'] },
  { label: 'Health', color: '#06b6d4', categories: ['pharmacy', 'optical_shop'] },
  { label: 'Services', color: '#ec4899', categories: ['salon', 'printing', 'mechanic', 'welding', 'battery_shop'] },
  { label: 'Agriculture', color: '#65a30d', categories: ['fertilizer', 'seed_shop', 'agricultural_equipment', 'tractor_dealer', 'animal_feed'] },
  { label: 'Hardware', color: '#78716c', categories: ['hardware', 'building_materials', 'stationery'] },
  { label: 'Hotels', color: '#f59e0b', categories: ['hotel'] },
  { label: 'Your business', color: '#111827', categories: [] },
]

function getColorForCategory(categoryCode?: string): string {
  if (!categoryCode || categoryCode === 'other') return '#9ca3af'
  return CATEGORY_COLORS[categoryCode] || '#dc2626'
}

export function BusinessMap({ center, businesses = [], competitors = [], markets = [], infrastructure = [], msmeClusters = [], showRadius = true, zoom = 12, height = '420px', selectedCategory }: BusinessMapProps) {
  const [layer, setLayer] = useState('all')

  // Determine which category_codes count as competitors for the selected business type.
  const competitorCodes = selectedCategory
    ? new Set(CATEGORY_COMPETITOR_MAP[selectedCategory] || [selectedCategory])
    : COMPETITOR_CATEGORIES

  // Layer toggles select which data the map shows (plan §26).
  const showBusinesses = layer === 'all' || layer === 'restaurants' || layer === 'retail'
  const showCompetitors = layer === 'all' || layer === 'competitors'
  const showMarkets = layer === 'all' || layer === 'markets'
  const showInfrastructure = layer === 'all' || layer === 'infrastructure'
  const showMsme = layer === 'all' || layer === 'msme'
  // `competitors` is passed explicitly when a venture is chosen (Market page).
  // On the 'competitors' layer alone we also derive them from the nearby
  // businesses so the Map page shows real pins instead of an empty set.
  // When a selectedCategory is provided, only businesses of matching competitor
  // categories are shown as red pins (fixes the "all categories in competitors" bug).
  const comps =
    layer === 'competitors'
      ? competitors.length
        ? competitors.filter((b) => !!b.category_code && competitorCodes.has(b.category_code))
        : businesses.filter((b) => !!b.category_code && competitorCodes.has(b.category_code))
      : showCompetitors
        ? competitors.filter((b) => !!b.category_code && competitorCodes.has(b.category_code))
        : []
  const msmes = showMsme ? msmeClusters : []
  const allShown = showBusinesses
    ? businesses.filter((b) => {
        if (layer === 'restaurants') return b.category_code === 'restaurant'
        if (layer === 'retail') return b.category_code === 'grocery' || b.category_code === 'textile'
        return true
      })
    : []

  const radius5 = createRadiusGeoJSON(center.latitude, center.longitude, 5, 'r5')
  const radius10 = createRadiusGeoJSON(center.latitude, center.longitude, 10, 'r10')

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height, width: '100%' }}>
      <div className="mb-2 flex shrink-0 flex-wrap gap-1">
        {layerOptions.map((l) => (
          <button
            key={l.key}
            onClick={() => setLayer(l.key)}
            className={`rounded-md px-2.5 py-1 text-xs font-medium ${
              layer === l.key ? 'bg-brand-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            {l.label}
          </button>
        ))}
      </div>
      <div style={{ flex: '1 1 auto', minHeight: 0, borderRadius: 12, overflow: 'hidden' }}>
        <Map latitude={center.latitude} longitude={center.longitude} zoom={zoom}>
          <MapControls navigation />
          {showRadius && <MapGeoJSON id="radius5" data={radius5} fillColor="#16a34a" fillOpacity={0.05} lineColor="#15803d" />}
          {showRadius && <MapGeoJSON id="radius10" data={radius10} fillOpacity={0.03} />}
          <MapMarker latitude={center.latitude} longitude={center.longitude} color="#111827" label="You are here" />
          <MapClusterLayer id="businesses" data={businessesToGeoJSON(allShown)} />
          {showMarkets && markets.length > 0 && (
            <MapGeoJSON id="markets" data={pointsToGeoJSON(markets)} circleColor="#d97706" />
          )}
          {showInfrastructure && infrastructure.length > 0 && (
            <MapGeoJSON id="infrastructure" data={infrastructureToGeoJSON(infrastructure)} circleColor="#7c3aed" circleRadius={5} />
)}
          {comps.map((c) => (
            <MapMarker
              key={c.id}
              latitude={c.latitude}
              longitude={c.longitude}
              color={getColorForCategory(c.category_code)}
              label={c.name}
              html
              popup={[
                `<strong>${c.name}</strong>`,
                c.metadata?.rating != null
                  ? `★ ${c.metadata.rating}${c.metadata.review_count != null ? ` · ${c.metadata.review_count} reviews` : ''}`
                  : null,
                c.address?.trim() || null,
                c.category_code && c.category_code !== 'other' ? `<span style="color:${getColorForCategory(c.category_code)};font-weight:600">${c.category_code.replace(/_/g, ' ')}</span>` : null,
                c.phone || null,
                c.distance_km != null ? `${c.distance_km} km away` : null,
                c.source_name || null,
              ]
                .filter(Boolean)
                .join('<br/>')}
            />
          ))}
          {msmes.map((m) => (
            <MapMarker
              key={m.pincode}
              latitude={m.latitude}
              longitude={m.longitude}
              color="#6366f1"
              label={`MSME pincode ${m.pincode} · ${m.total}`}
              html
              popup={[
                `<strong>Pincode ${m.pincode}</strong> · ${m.total} registered MSME units`,
                `${m.activity_codes} activity types`,
                m.distance_km != null ? `${m.distance_km} km away` : null,
                m.units && m.units.length ? `e.g. ${m.units.slice(0, 6).map((u) => u.name).join(', ')}${m.units.length > 6 ? ', …' : ''}` : null,
                '<em>Pincode centroid (units resolve to pincode, not street)</em>',
              ]
                .filter(Boolean)
                .join('<br/>')}
            />
          ))}
        </Map>
      </div>
      {/* Legend */}
      {showCompetitors && comps.length > 0 && (
        <div className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5">
          {LEGEND_GROUPS.filter(g => g.categories.length > 0).map((g) => {
            const count = comps.filter(b => g.categories.includes(b.category_code || '')).length
            if (count === 0) return null
            return (
              <span key={g.label} className="flex items-center gap-1 text-[10px] text-gray-500">
                <span className="inline-block h-2 w-2 rounded-full" style={{ backgroundColor: g.color }} />
                {g.label} ({count})
              </span>
            )
          })}
          <span className="flex items-center gap-1 text-[10px] text-gray-500">
            <span className="inline-block h-2 w-2 rounded-full bg-gray-11" style={{ backgroundColor: '#111827' }} />
            Your business
          </span>
        </div>
      )}
      <p className="mt-1 shrink-0 text-[10px] text-gray-400">© OpenStreetMap contributors. Mapped business data may be incomplete.</p>
    </div>
  )
}
