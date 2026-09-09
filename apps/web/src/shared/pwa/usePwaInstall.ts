import { useCallback, useEffect, useState } from "react"

const DISMISS_KEY = "contentos_pwa_install_dismissed"
const DISMISS_TTL_MS = 7 * 24 * 60 * 60 * 1000

export type BeforeInstallPromptEvent = Event & {
  readonly platforms: string[]
  readonly userChoice: Promise<{ outcome: "accepted" | "dismissed"; platform: string }>
  prompt: () => Promise<void>
}

declare global {
  interface WindowEventMap {
    beforeinstallprompt: BeforeInstallPromptEvent
  }
}

function isStandaloneDisplay(): boolean {
  if (typeof window === "undefined") return false
  const mq = window.matchMedia("(display-mode: standalone)").matches
  const iosStandalone =
    "standalone" in navigator &&
    Boolean((navigator as Navigator & { standalone?: boolean }).standalone)
  return mq || iosStandalone
}

function isDismissed(): boolean {
  try {
    const raw = localStorage.getItem(DISMISS_KEY)
    if (!raw) return false
    const ts = Number(raw)
    if (!Number.isFinite(ts)) return false
    if (Date.now() - ts > DISMISS_TTL_MS) {
      localStorage.removeItem(DISMISS_KEY)
      return false
    }
    return true
  } catch {
    return false
  }
}

function isIosSafari(): boolean {
  if (typeof navigator === "undefined") return false
  const ua = navigator.userAgent
  const iOS = /iPad|iPhone|iPod/.test(ua) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1)
  const webkit = /WebKit/.test(ua)
  const chromeIos = /CriOS|FxiOS|EdgiOS/.test(ua)
  return iOS && webkit && !chromeIos
}

export type PwaInstallState = {
  /** Banner should be visible */
  visible: boolean
  /** Native install is available via beforeinstallprompt */
  canInstall: boolean
  /** Show iOS Add-to-Home-Screen hint */
  iosHint: boolean
  installing: boolean
  install: () => Promise<void>
  dismiss: () => void
}

export function usePwaInstall(): PwaInstallState {
  const [deferred, setDeferred] = useState<BeforeInstallPromptEvent | null>(null)
  const [installed, setInstalled] = useState(() => isStandaloneDisplay())
  const [dismissed, setDismissed] = useState(() => isDismissed())
  const [installing, setInstalling] = useState(false)

  useEffect(() => {
    const onBip = (e: BeforeInstallPromptEvent) => {
      e.preventDefault()
      setDeferred(e)
    }
    const onInstalled = () => {
      setInstalled(true)
      setDeferred(null)
      try {
        localStorage.removeItem(DISMISS_KEY)
      } catch {
        /* ignore */
      }
    }
    const onDisplayChange = (ev: MediaQueryListEvent) => {
      if (ev.matches) setInstalled(true)
    }
    const mq = window.matchMedia("(display-mode: standalone)")

    window.addEventListener("beforeinstallprompt", onBip)
    window.addEventListener("appinstalled", onInstalled)
    mq.addEventListener?.("change", onDisplayChange)

    return () => {
      window.removeEventListener("beforeinstallprompt", onBip)
      window.removeEventListener("appinstalled", onInstalled)
      mq.removeEventListener?.("change", onDisplayChange)
    }
  }, [])

  const dismiss = useCallback(() => {
    setDismissed(true)
    try {
      localStorage.setItem(DISMISS_KEY, String(Date.now()))
    } catch {
      /* ignore */
    }
  }, [])

  const install = useCallback(async () => {
    if (!deferred) return
    setInstalling(true)
    try {
      await deferred.prompt()
      const choice = await deferred.userChoice
      if (choice.outcome === "accepted") {
        setInstalled(true)
        setDeferred(null)
      }
    } finally {
      setInstalling(false)
    }
  }, [deferred])

  const iosHint = !installed && !dismissed && !deferred && isIosSafari()
  const canInstall = Boolean(deferred) && !installed && !dismissed
  const visible = !installed && !dismissed && (canInstall || iosHint)

  return {
    visible,
    canInstall,
    iosHint,
    installing,
    install,
    dismiss,
  }
}
