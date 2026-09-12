import { Download, Share, X } from "lucide-react"
import { AnimatePresence, motion } from "framer-motion"
import { Button } from "@/components/ui/button"
import { cn } from "@/shared/lib/utils"
import { usePwaInstall } from "@/shared/pwa/usePwaInstall"

/**
 * In-flow top banner. Install App triggers Chrome's native install dialog
 * (same UI as Android Chrome ⋮ → Install app).
 */
export function InstallPrompt({ className }: { className?: string }) {
  const { visible, canInstall, browserHint, iosHint, installing, install, dismiss } =
    usePwaInstall()

  const subtitle = iosHint
    ? "Tap Share, then “Add to Home Screen”. Website still opens in Safari anytime."
    : canInstall
      ? "Creates a home-screen app. Your site keeps working normally in Chrome too."
      : "Use ⋮ → Install and create shortcut. Browser tab will keep working as usual."

  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          role="region"
          aria-label="Install ContentOS app"
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: "auto", opacity: 1 }}
          exit={{ height: 0, opacity: 0 }}
          transition={{ duration: 0.25 }}
          className={cn("relative z-40 overflow-hidden", className)}
        >
          <div
            className={cn(
              "border-b border-border bg-card/90 backdrop-blur-md",
              "px-3 py-2.5 sm:px-4",
              "pt-[max(0.625rem,env(safe-area-inset-top))]",
            )}
          >
            <div className="mx-auto flex max-w-5xl items-center gap-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-linear-to-br from-primary to-secondary font-display text-sm font-semibold text-primary-foreground shadow-glow">
                C
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium leading-tight truncate">
                  Install & create shortcut
                </p>
                <p className="text-[11px] sm:text-xs text-muted-foreground leading-snug mt-0.5">
                  {subtitle}
                </p>
              </div>
              <div className="flex items-center gap-1.5 shrink-0">
                {canInstall && (
                  <Button
                    size="sm"
                    className="rounded-xl gap-1.5 min-h-10 px-3"
                    disabled={installing}
                    onClick={() => void install()}
                  >
                    <Download className="h-3.5 w-3.5" />
                    <span>{installing ? "Installing…" : "Install"}</span>
                  </Button>
                )}
                {iosHint && (
                  <span className="inline-flex items-center gap-1 rounded-xl border border-border bg-muted/50 px-2.5 py-2 text-[11px] text-muted-foreground min-h-10">
                    <Share className="h-3.5 w-3.5 text-primary" />
                    Share
                  </span>
                )}
                {browserHint && (
                  <span className="hidden sm:inline-flex items-center gap-1 rounded-xl border border-primary/30 bg-primary/10 px-2.5 py-2 text-[11px] text-primary min-h-10">
                    <Download className="h-3.5 w-3.5" />
                    Chrome ⋮
                  </span>
                )}
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="rounded-xl h-10 w-10 px-0"
                  aria-label="Dismiss install prompt"
                  onClick={dismiss}
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
