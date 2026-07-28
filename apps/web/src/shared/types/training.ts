export type OfferingItem = {
  name: string
  description: string
  differentiators: string[]
  proof_points: string[]
}

export type FaqItem = { question: string; answer: string }

export type DocumentRef = {
  title: string
  category: "product" | "case_study" | "guideline" | "other"
  body: string
  priority: number
}

export type TenantTrainingSchema = {
  schema_version: string
  company: {
    legal_name: string
    display_name: string
    industry: string
    website: string
    phone: string
    email: string
    hq_location: string
    operating_regions: string[]
    company_size_band: string
    founded_year: number | null
    one_liner: string
  }
  audience: {
    icp_titles: string[]
    icp_industries: string[]
    buyer_pain_points: string[]
    linkedin_audience_notes: string
  }
  offerings: OfferingItem[]
  messaging: {
    tone: string[]
    voice_dos: string[]
    voice_donts: string[]
    banned_claims: string[]
    compliance_notes: string
    cta_styles: string[]
    hashtag_policy: string
    linkedin_post_length_preference: string
  }
  brand_visual: {
    primary_color: string
    secondary_color: string
    accent_color: string
    logo_url: string
    visual_style_keywords: string[]
    image_do_nots: string[]
    app_display_name: string
    ui_mode: "platform" | "white_label"
  }
  approved_facts: string[]
  faq: FaqItem[]
  documents: DocumentRef[]
}

export const emptyTraining = (): TenantTrainingSchema => ({
  schema_version: "1",
  company: {
    legal_name: "",
    display_name: "",
    industry: "",
    website: "",
    phone: "",
    email: "",
    hq_location: "",
    operating_regions: [],
    company_size_band: "",
    founded_year: null,
    one_liner: "",
  },
  audience: {
    icp_titles: [],
    icp_industries: [],
    buyer_pain_points: [],
    linkedin_audience_notes: "",
  },
  offerings: [],
  messaging: {
    tone: [],
    voice_dos: [],
    voice_donts: [],
    banned_claims: [],
    compliance_notes: "",
    cta_styles: [],
    hashtag_policy: "",
    linkedin_post_length_preference: "medium",
  },
  brand_visual: {
    primary_color: "",
    secondary_color: "",
    accent_color: "",
    logo_url: "",
    visual_style_keywords: [],
    image_do_nots: [],
    app_display_name: "",
    ui_mode: "platform",
  },
  approved_facts: [],
  faq: [],
  documents: [],
})
