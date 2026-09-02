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
  // ── Navigation ──
  navAnalyze: { en: 'Analyze', ta: 'பகுப்பாய்வு', hi: 'विश्लेषण' },
  navDashboard: { en: 'Dashboard', ta: 'டாஷ்போர்டு', hi: 'डैशबोर्ड' },
  navMarket: { en: 'Market', ta: 'சந்தை', hi: 'बाजार' },
  navMap: { en: 'Map', ta: 'வரைபடம்', hi: 'नक्शा' },
  navFinance: { en: 'Finance', ta: 'நிதி', hi: 'वित्त' },
  navSimulator: { en: 'Simulator', ta: 'உருவகப்படுத்தி', hi: 'सिम्युलेटर' },
  navReport: { en: 'Report', ta: 'அறிக்கை', hi: 'रिपोर्ट' },
  navSchemes: { en: 'Schemes', ta: 'திட்டங்கள்', hi: 'योजनाएं' },
  navData: { en: 'Data', ta: 'தரவு', hi: 'डेटा' },
  // ── Landing / common ──
  subtitle: {
    en: 'Hyper-Local Business Intelligence',
    ta: 'ஹைப்பர்-லோக்கல் வணிக நுண்ணறிவு',
    hi: 'हाइपर-लोकल व्यावसायिक बुद्धिमत्ता',
  },
  footer: {
    en: '© OpenStreetMap contributors · GramBiz AI demo — scores and loan guidance are estimates, not guarantees.',
    ta: '© OpenStreetMap பங்களிப்பாளர்கள் · GramBiz AI டெமோ — மதிப்பெண்கள் மற்றும் கடன் வழிகாட்டி மதிப்பீடுகள், உத்தரவாதங்கள் அல்ல.',
    hi: '© OpenStreetMap योगदानकर्ता · GramBiz AI डेमो — स्कोर और ऋण मार्गदर्शन अनुमान हैं, गारंटी नहीं।',
  },
  // ── Advisory (SIH26091 NLP) ──
  advisoryTitle: {
    en: 'Describe your business in plain words (Multilingual)',
    ta: 'உங்கள் தொழிலை எளிய வார்த்தைகளில் விவரிக்கவும் (பல மொழி)',
    hi: 'अपने व्यवसाय का सरल शब्दों में वर्णन करें (बहुभाषी)',
  },
  advisorySubtitle: {
    en: 'Type or paste a sentence in English, தமிழ், or हिंदी. GramBiz extracts the details, pre-fills the form, and can generate a full advisory plan.',
    ta: 'ஆங்கிலம், தமிழ் அல்லது இந்தியில் ஒரு வாக்கியத்தைத் தட்டச்சு செய்யவும். GramBiz விவரங்களைப் பிரித்தெடுத்து, படிவத்தை முன்கூட்டியே நிரப்பி, முழு ஆலோசனைத் திட்டத்தை உருவாக்கும்.',
    hi: 'अंग्रेज़ी, தமிழ் या हिंदी में एक वाक्य टाइप करें। GramBiz विवरण निकालता है, फॉर्म भरता है, और पूरी सलाह योजना बना सकता है।',
  },
  advisoryPlaceholder: {
    en: 'e.g. I want to start dairy farming in Erode, Tamil Nadu with a budget around 2 lakh. Or: ஈரோடு மாவட்டத்தில் பால் பண்ணை தொடங்க 2 லட்சம் பட்ஜெட்.',
    ta: 'எ.கா. ஈரோடு மாவட்டத்தில் பால் பண்ணை தொடங்க 2 லட்சம் பட்ஜெட். Or: I want to start dairy farming in Erode with a budget around 2 lakh.',
    hi: 'उदा. ईरोड जिले में 2 लाख बजट के साथ डेयरी फार्मिंग शुरू करना चाहता हूँ। Or: I want to start dairy farming in Erode, budget 2 lakh.',
  },
  parsePrefill: { en: 'Parse & Pre-fill form', ta: 'பகுப்பாய்வு & படிவத்தை நிரப்பு', hi: 'पार्स करें और फॉर्म भरें' },
  fullAdvisory: { en: 'Generate Full Advisory Report', ta: 'முழு ஆலோசனை அறிக்கையை உருவாக்கு', hi: 'पूर्ण सलाह रिपोर्ट बनाएं' },
  parsing: { en: 'Parsing…', ta: 'பகுப்பாய்வு நடக்கிறது…', hi: 'पार्स हो रहा है…' },
  generating: { en: 'Generating…', ta: 'உருவாக்குகிறது…', hi: 'बना रहा है…' },
  fullReportTitle: { en: 'Full Advisory Report', ta: 'முழு ஆலோசனை அறிக்கை', hi: 'पूर्ण सलाह रिपोर्ट' },
  bestSchemes: { en: 'Best matching schemes', ta: 'சிறந்த பொருந்தும் திட்டங்கள்', hi: 'सर्वोत्तम मेल खाती योजनाएँ' },
  loanStructure: { en: 'Loan structure', ta: 'கடன் அமைப்பு', hi: 'ऋण संरचना' },
  keyRisks: { en: 'Key risks', ta: 'முக்கிய இடர்கள்', hi: 'मुख्य जोखिम' },
  documentsNeeded: { en: 'Documents you may need', ta: 'உங்களுக்குத் தேவையான ஆவணங்கள்', hi: 'आपको चाहिए दस्तावेज़' },
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
