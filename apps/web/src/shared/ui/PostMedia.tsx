import { useEffect, useState } from "react"
import { createPortal } from "react-dom"
import { Download, Eye, X, ZoomIn } from "lucide-react"
import { Button } from "@/components/ui/button"
import { downloadMedia, mediaSrc } from "@/shared/lib/media"
import { cn } from "@/shared/lib/utils"

type Props = {
  imageUrl?: string | null
  filename?: string
  className?: string
  imgClassName?: string
  /** Compact card: smaller actions, no extra vertical chrome */
  compact?: boolean
}

export function PostMedia({
  imageUrl,
  filename = "linkedin-post.png",
  className,
  imgClassName,
  compact = false,
}: Props) {
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const src = mediaSrc(imageUrl)

  useEffect(() => {
    if (!open) return
    const prev = document.body.style.overflow
    document.body.style.overflow = "hidden"
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false)
    }
    window.addEventListener("keydown", onKey)
    return () => {
      document.body.style.overflow = prev
      window.removeEventListener("keydown", onKey)
    }
  }, [open])

  if (!src) return null

  const onDownload = async () => {
    setBusy(true)
    try {
      await downloadMedia(src, filename)
    } catch {
      window.open(src, "_blank", "noopener,noreferrer")
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <div className={cn("relative group", className)}>
        <button
          type="button"
          className="relative block w-full overflow-hidden bg-muted"
          onClick={() => setOpen(true)}
        >
          <img
            src={src}
            alt=""
            className={cn(
              compact
                ? "w-full aspect-[1.91/1] object-contain object-center bg-black/5"
                : "w-full aspect-[16/9] object-cover object-center",
              imgClassName,
            )}
          />
          <span className="absolute inset-0 bg-gradient-to-t from-black/55 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none" />
          <span className="absolute bottom-2 left-2 inline-flex items-center gap-1.5 rounded-full bg-black/55 backdrop-blur-md px-2.5 py-1 text-[11px] text-white opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
            <ZoomIn className="h-3 w-3" />
            Preview
          </span>
          {compact && (
            <span className="absolute top-2 right-2 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
              <Button
                type="button"
                size="sm"
                variant="secondary"
                className="h-7 rounded-lg px-2 text-[11px]"
                disabled={busy}
                onClick={(e) => {
                  e.stopPropagation()
                  void onDownload()
                }}
              >
                <Download className="h-3 w-3" />
              </Button>
            </span>
          )}
        </button>
        {!compact && (
          <div className="flex gap-2 p-3">
            <Button type="button" size="sm" variant="outline" onClick={() => setOpen(true)}>
              <Eye className="h-3.5 w-3.5" />
              View
            </Button>
            <Button
              type="button"
              size="sm"
              variant="secondary"
              disabled={busy}
              onClick={() => void onDownload()}
            >
              <Download className="h-3.5 w-3.5" />
              {busy ? "…" : "Download"}
            </Button>
          </div>
        )}
      </div>

      {open &&
        createPortal(
          <div
            className="fixed inset-0 z-[100] flex items-center justify-center bg-black/80 p-4"
            onClick={() => setOpen(false)}
            role="dialog"
            aria-modal
          >
            <button
              type="button"
              className="absolute top-4 right-4 rounded-full bg-white/10 p-2 text-white hover:bg-white/20"
              onClick={() => setOpen(false)}
            >
              <X className="h-5 w-5" />
            </button>
            <img
              src={src}
              alt=""
              className="max-h-[90vh] max-w-[95vw] object-contain rounded-lg shadow-2xl"
              onClick={(e) => e.stopPropagation()}
            />
          </div>,
          document.body,
        )}
    </>
  )
}
