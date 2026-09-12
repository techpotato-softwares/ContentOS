export type OnboardingStepKey =
  | "linkedin"
  | "training"
  | "generate"
  | "review"
  | "publish"

export type OnboardingStepState = {
  status: "pending" | "completed"
  completedAt?: string | null
}

export type OnboardingState = {
  version: number
  steps: Record<OnboardingStepKey, OnboardingStepState>
  skipped: boolean
  completedAt?: string | null
  showWizard: boolean
  allComplete: boolean
}

export type OnboardingStepDef = {
  key: OnboardingStepKey
  title: string
  description: string
  href: string
  cta: string
}

export const ONBOARDING_STEPS: OnboardingStepDef[] = [
  {
    key: "linkedin",
    title: "Connect LinkedIn",
    description: "Link your personal profile or company page so ContentOS can publish.",
    href: "/connections/linkedin?from=onboarding",
    cta: "Open LinkedIn",
  },
  {
    key: "training",
    title: "Train brand",
    description: "Save your company voice, domain, and brand kit.",
    href: "/settings/training?from=onboarding",
    cta: "Open Training",
  },
  {
    key: "generate",
    title: "Generate posts",
    description: "Create your first batch of LinkedIn variants from a brief.",
    href: "/agent?from=onboarding",
    cta: "Open Agent",
  },
  {
    key: "review",
    title: "Review drafts",
    description: "Approve a draft before it goes live.",
    href: "/review?from=onboarding",
    cta: "Open Review",
  },
  {
    key: "publish",
    title: "First publish",
    description: "Publish an approved post to LinkedIn to finish setup.",
    href: "/review?from=onboarding&status=approved",
    cta: "Publish from Review",
  },
]

export function isStepDone(state: OnboardingState | undefined, key: OnboardingStepKey): boolean {
  return state?.steps?.[key]?.status === "completed"
}

export function nextPendingStep(
  state: OnboardingState | undefined,
): OnboardingStepDef | undefined {
  if (!state) return ONBOARDING_STEPS[0]
  return ONBOARDING_STEPS.find((s) => !isStepDone(state, s.key))
}

export function completedStepCount(state: OnboardingState | undefined): number {
  if (!state) return 0
  return ONBOARDING_STEPS.filter((s) => isStepDone(state, s.key)).length
}
