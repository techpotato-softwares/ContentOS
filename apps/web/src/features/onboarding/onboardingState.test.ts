/**
 * Lightweight frontend onboarding helper checks (no vitest runner required).
 * Run: node --experimental-strip-types src/features/onboarding/onboardingState.test.ts
 * or: npx tsx src/features/onboarding/onboardingState.test.ts
 */
import {
  ONBOARDING_STEPS,
  completedStepCount,
  isStepDone,
  nextPendingStep,
  type OnboardingState,
} from "./onboardingState.ts"

function assert(cond: unknown, msg: string) {
  if (!cond) throw new Error(msg)
}

const empty: OnboardingState = {
  version: 1,
  steps: {
    linkedin: { status: "pending", completedAt: null },
    training: { status: "pending", completedAt: null },
    generate: { status: "pending", completedAt: null },
    review: { status: "pending", completedAt: null },
    publish: { status: "pending", completedAt: null },
  },
  skipped: false,
  completedAt: null,
  showWizard: true,
  allComplete: false,
}

assert(ONBOARDING_STEPS.length === 5, "expected 5 wizard steps")
assert(
  ONBOARDING_STEPS.every((s) => s.href.includes("from=onboarding")),
  "each step should deep-link with from=onboarding",
)
assert(ONBOARDING_STEPS[0].href.startsWith("/connections/linkedin"), "linkedin href")
assert(ONBOARDING_STEPS[1].href.startsWith("/settings/training"), "training href")
assert(ONBOARDING_STEPS[2].href.startsWith("/agent"), "agent href")
assert(ONBOARDING_STEPS[3].href.startsWith("/review"), "review href")
assert(ONBOARDING_STEPS[4].href.startsWith("/review"), "publish href")

assert(nextPendingStep(empty)?.key === "linkedin", "first pending is linkedin")
assert(completedStepCount(empty) === 0, "no steps done")

const mid: OnboardingState = {
  ...empty,
  steps: {
    ...empty.steps,
    linkedin: { status: "completed", completedAt: "2026-01-01T00:00:00Z" },
    training: { status: "completed", completedAt: "2026-01-01T00:00:00Z" },
  },
}
assert(isStepDone(mid, "linkedin"), "linkedin done")
assert(nextPendingStep(mid)?.key === "generate", "next is generate")
assert(completedStepCount(mid) === 2, "two done")

console.log("onboardingState tests passed")
