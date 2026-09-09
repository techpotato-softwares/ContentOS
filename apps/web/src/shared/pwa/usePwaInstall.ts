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
  const iOS =
    /iPad|iPhone|iPod/.test(ua) ||
    (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1)
  const webkit = /WebKit/.test(ua)
  const chromeIos = /CriOS|FxiOS|EdgiOS/.test(ua)
  return iOS && webkit && !chromeIos
}

export type PwaInstallState = {
  visible: boolean
  /** Chrome/Edge fired beforeinstallprompt — Install opens native dialog */
  canInstall: boolean
  browserHint: boolean
  iosHint: boolean
  installing: boolean
  install: () => Promise<void>
  dismiss: () => void
}

/**
 * Drives install UI. Native Android Chrome ⋮ → Install app appears when the site
 * is installable (manifest + SW + HTTPS); that menu is controlled by Chrome.
 * Our banner Install button calls event.prompt() for the same system dialog.
 */
export function usePwaInstall(): PwaInstallState {
  const [deferred, setDeferred] = useState<BeforeInstallPromptEvent | null>(null)
  const [installed, setInstalled] = useState(() => isStandaloneDisplay())
  const [dismissed, setDismissed] = useState(() => isDismissed())
  const [installing, setInstalling] = useState(false)
  const [pwaReady, setPwaReady] = useState(false)

  useEffect(() => {
    const onBip = (e: BeforeInstallPromptEvent) => {
      // Capture so we can open the same native Install dialog as Chrome ⋮ menu
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

    let cancelled = false
    void (async () => {
      try {
        const hasManifest = Boolean(
          document.querySelector('link[rel="manifest"]'),
        )
        let swOk = false
        if ("serviceWorker" in navigator) {
          const reg = await navigator.serviceWorker.ready
          swOk = Boolean(reg.active)
        }
        if (!cancelled) setPwaReady(hasManifest && swOk)
      } catch {
        if (!cancelled) setPwaReady(false)
      }
    })()

    return () => {
      cancelled = true
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
      // Opens Chrome's native "Install app" dialog (same as ⋮ → Install app)
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
  const browserHint =
    !installed && !dismissed && !canInstall && !iosHint && pwaReady
  const visible = !installed && !dismissed && (canInstall || iosHint || browserHint)

  return {
    visible,
    canInstall,
    browserHint,
    iosHint,
    installing,
    install,
    dismiss,
  }
}
