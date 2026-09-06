import { Link, useLocation } from "react-router-dom"
import { useEffect } from "react"
import { Check, Circle } from "lucide-react"
import {
  useCompleteOnboardingStepMutation,
  useGetOnboardingQuery,
  useSkipOnboardingMutation,
} from "@/features/api/contentApi"
import { Button } from "@/components/ui/button"
import { cn } from "@/shared/lib/utils"

const STEPS = [
  {
    id: "linkedin" as const,
    label: "Connect LinkedIn",
    to: "/connections/linkedin",
    hint: "Authorize your profile or company page",
  },
  {
    id: "training" as const,
    label: "Company training",
    to: "/settings/training",
    hint: "Save brand context so posts stay on-message",
  },
  {
    id: "generate" as const,
    label: "Generate a post",
    to: "/agent",
    hint: "Create your first draft in the agent",
  },
  {
    id: "publish" as const,
    label: "Review & publish",
    to: "/review",
    hint: "Approve and publish to LinkedIn",
  },
]

/** First-run wizard — deep-links to existing flows; hidden when completed/skipped. */
export function OnboardingWizard() {
  const location = useLocation()
  const { data, isLoading, refetch } = useGetOnboardingQuery()
  const [skip, skipState] = useSkipOnboardingMutation()
  const [completeStep] = useCompleteOnboardingStepMutation()

  useEffect(() => {
    void refetch()
  }, [location.pathname, refetch])

  if (isLoading || !data?.visible) return null

  const steps = data.steps
  const current =
    STEPS.find((s) => !steps[s.id]) || STEPS[STEPS.length - 1]

  const onSkip = async () => {
    await skip().unwrap()
  }

  const tryCompleteCurrent = async () => {
    try {
      await completeStep(current.id).unwrap()
    } catch {
      void refetch()
    }
  }

  return (
    <div className="mb-4 rounded-2xl border border-border bg-background/50 px-4 py-3 shrink-0">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="font-medium text-sm">Get started with ContentOS</p>
          <p className="text-xs text-muted-foreground mt-0.5">
            Finish these steps once — we save progress for your company.
          </p>
        </div>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          disabled={skipState.isLoading}
          onClick={() => void onSkip()}
        >
          Skip
        </Button>
      </div>
      <ol className="mt-3 flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center sm:gap-1">
        {STEPS.map((step, i) => {
          const done = !!steps[step.id]
          const active = current.id === step.id && !done
          const onThisPage = location.pathname === step.to
          return (
            <li key={step.id} className="flex items-center gap-2 min-w-0">
              {i > 0 && (
                <span className="hidden sm:inline text-muted-foreground px-1" aria-hidden>
                  →
                </span>
              )}
              <Link
                to={step.to}
                className={cn(
                  "flex items-center gap-2 rounded-xl px-2.5 py-1.5 text-sm transition-colors min-w-0",
                  done && "text-primary",
                  active && "bg-primary/10 text-foreground",
                  !done && !active && "text-muted-foreground hover:text-foreground",
                )}
                onClick={() => {
                  if (onThisPage && !done) void tryCompleteCurrent()
                }}
              >
                {done ? (
                  <Check className="h-4 w-4 shrink-0" aria-hidden />
                ) : (
                  <Circle
                    className={cn("h-3.5 w-3.5 shrink-0", active && "fill-primary/30")}
                    aria-hidden
                  />
                )}
                <span className="truncate">
                  <span className="font-medium">
                    {i + 1}. {step.label}
                  </span>
                  {active && (
                    <span className="hidden md:inline text-xs text-muted-foreground ml-1">
                      — {step.hint}
                    </span>
                  )}
                </span>
              </Link>
            </li>
          )
        })}
      </ol>
    </div>
  )
}
