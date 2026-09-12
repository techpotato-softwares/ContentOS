import { Link } from "react-router-dom"
import { motion } from "framer-motion"
import {
  CheckCircle2,
  Circle,
  ArrowRight,
  SkipForward,
  Sparkles,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  useGetOnboardingQuery,
  usePutOnboardingMutation,
} from "@/features/api/contentApi"
import {
  ONBOARDING_STEPS,
  completedStepCount,
  isStepDone,
  nextPendingStep,
} from "./onboardingState"
import { cn } from "@/shared/lib/utils"

export function OnboardingPage() {
  const { data, isLoading, error, refetch } = useGetOnboardingQuery()
  const [putOnboarding, putState] = usePutOnboardingMutation()
  const done = completedStepCount(data)
  const total = ONBOARDING_STEPS.length
  const next = nextPendingStep(data)
  const finished = Boolean(data?.allComplete || data?.completedAt || data?.skipped)

  const skip = async () => {
    await putOnboarding({ skipped: true }).unwrap()
  }

  const reopen = async () => {
    await putOnboarding({ skipped: false, reopen: true }).unwrap()
  }

  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <section className="relative overflow-hidden rounded-3xl border border-border bg-linear-to-br from-primary/12 via-background/50 to-secondary/10 p-6 md:p-8">
        <div className="flex items-start gap-3">
          <span className="mt-0.5 flex h-10 w-10 items-center justify-center rounded-2xl bg-primary/15 text-primary">
            <Sparkles className="h-5 w-5" />
          </span>
          <div className="min-w-0 flex-1">
            <h1 className="font-display text-2xl md:text-3xl tracking-tight">
              Get ContentOS ready
            </h1>
            <p className="mt-2 text-sm text-muted-foreground max-w-xl">
              Connect LinkedIn, train your brand, generate drafts, review, then publish.
              Each step opens the real feature — progress is saved across refresh and login.
            </p>
            <div className="mt-4 flex flex-wrap items-center gap-3">
              <div className="text-xs font-medium text-muted-foreground">
                {done} of {total} steps complete
              </div>
              <div className="h-1.5 w-40 overflow-hidden rounded-full bg-muted">
                <motion.div
                  className="h-full rounded-full bg-primary"
                  initial={{ width: 0 }}
                  animate={{ width: `${(done / total) * 100}%` }}
                  transition={{ duration: 0.4 }}
                />
              </div>
            </div>
          </div>
        </div>
      </section>

      {isLoading && (
        <p className="text-sm text-muted-foreground">Loading setup progress…</p>
      )}
      {error && (
        <div className="rounded-2xl border border-destructive/30 bg-destructive/5 p-4 text-sm">
          Could not load onboarding state.{" "}
          <button type="button" className="underline" onClick={() => refetch()}>
            Retry
          </button>
        </div>
      )}

      {finished ? (
        <div className="rounded-3xl border border-border bg-muted/30 p-6 space-y-4">
          <h2 className="font-display text-xl">
            {data?.skipped ? "Setup skipped" : "You're all set"}
          </h2>
          <p className="text-sm text-muted-foreground">
            {data?.skipped
              ? "You can reopen this guide anytime from Team settings."
              : "Your first publish finished onboarding. Jump back into the agent anytime."}
          </p>
          <div className="flex flex-wrap gap-2">
            <Button asChild className="rounded-xl">
              <Link to="/agent">Go to Agent</Link>
            </Button>
            <Button asChild variant="outline" className="rounded-xl">
              <Link to="/dashboard">Dashboard</Link>
            </Button>
            {data?.skipped && (
              <Button
                variant="ghost"
                className="rounded-xl"
                disabled={putState.isLoading}
                onClick={() => void reopen()}
              >
                Reopen wizard
              </Button>
            )}
          </div>
        </div>
      ) : (
        <>
          <ol className="space-y-3">
            {ONBOARDING_STEPS.map((step, idx) => {
              const complete = isStepDone(data, step.key)
              const isNext = next?.key === step.key
              return (
                <motion.li
                  key={step.key}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: idx * 0.05 }}
                  className={cn(
                    "rounded-3xl border p-4 md:p-5 flex flex-col sm:flex-row sm:items-center gap-4",
                    complete
                      ? "border-primary/25 bg-primary/5"
                      : isNext
                        ? "border-primary/40 bg-background/60 shadow-glow"
                        : "border-border bg-muted/20",
                  )}
                >
                  <div className="flex items-start gap-3 flex-1 min-w-0">
                    {complete ? (
                      <CheckCircle2 className="h-5 w-5 text-primary shrink-0 mt-0.5" />
                    ) : (
                      <Circle
                        className={cn(
                          "h-5 w-5 shrink-0 mt-0.5",
                          isNext ? "text-primary" : "text-muted-foreground",
                        )}
                      />
                    )}
                    <div className="min-w-0">
                      <div className="text-xs uppercase tracking-wide text-muted-foreground">
                        Step {idx + 1}
                      </div>
                      <h3 className="font-medium text-base">{step.title}</h3>
                      <p className="text-sm text-muted-foreground mt-1">{step.description}</p>
                    </div>
                  </div>
                  {!complete && (
                    <Button asChild className="rounded-xl shrink-0" variant={isNext ? "default" : "outline"}>
                      <Link to={step.href}>
                        {step.cta}
                        <ArrowRight className="h-4 w-4 ml-1" />
                      </Link>
                    </Button>
                  )}
                  {complete && (
                    <span className="text-xs font-medium text-primary shrink-0">Done</span>
                  )}
                </motion.li>
              )
            })}
          </ol>

          <div className="flex flex-wrap items-center gap-3 pt-2">
            {next && (
              <Button asChild className="rounded-xl">
                <Link to={next.href}>
                  Continue: {next.title}
                  <ArrowRight className="h-4 w-4 ml-1" />
                </Link>
              </Button>
            )}
            <Button
              variant="ghost"
              className="rounded-xl text-muted-foreground"
              disabled={putState.isLoading}
              onClick={() => void skip()}
            >
              <SkipForward className="h-4 w-4 mr-1" />
              Skip setup
            </Button>
          </div>
        </>
      )}
    </div>
  )
}
