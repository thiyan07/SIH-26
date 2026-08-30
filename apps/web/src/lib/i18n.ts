export type Language = 'en' | 'ta' | 'hi'

const dict = {
  analyzeBusiness: {
    en: 'Analyze My Business',
    ta: 'என் தொழிலை பகுப்பாய்வு செய்',
    hi: 'मेरे व्यवसाय का विश्लेषण करें',
  },
  exploreDemo: {
    en: 'Explore Demo',
    ta: 'டெமோவை பார்க்க',
    hi: 'डेमो देखें',
  },
  opportunity: {
    en: 'Overall Opportunity',
    ta: 'ஒட்டுமொத்த வாய்ப்பு',
    hi: 'समग्र अवसर',
  },
  confidence: {
    en: 'Confidence',
    ta: 'நம்பகத்தன்மை',
    hi: 'विश्वास',
  },
  demand: {
    en: 'Market Demand',
    ta: 'சந்தை தேவை',
    hi: 'बाजार मांग',
  },
  competition: {
    en: 'Competition',
    ta: 'போட்டி',
    hi: 'प्रतिस्पर्धा',
  },
  accessibility: {
    en: 'Accessibility',
    ta: 'அணுகல்',
    hi: 'पहुंच',
  },
  financialFit: {
    en: 'Financial Fit',
    ta: 'நிதி பொருத்தம்',
    hi: 'वित्तीय फिट',
  },
  risk: {
    en: 'Risk',
    ta: 'இடர்',
    hi: 'जोखिम',
  },
  go: { en: 'GO', ta: 'செய்யலாம்', hi: 'जाएं' },
  modify: { en: 'MODIFY', ta: 'மாற்றி செய்யலாம்', hi: 'संशोधित करें' },
  avoid: { en: 'AVOID', ta: 'தவிர்க்கவும்', hi: 'टालें' },
} as const

export function tr(key: keyof typeof dict, lang: Language): string {
  return (dict[key] && dict[key][lang]) || dict[key].en
}

export function recommendationLabel(label: string, lang: Language): string {
  if (label === 'GO') return tr('go', lang)
  if (label === 'MODIFY') return tr('modify', lang)
  if (label === 'AVOID') return tr('avoid', lang)
  return label
}
