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
}

export function PostMedia({ imageUrl, filename = "linkedin-post.png", className, imgClassName }: Props) {
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
            className={cn("w-full aspect-[16/9] object-cover object-center", imgClassName)}
          />
          <span className="absolute inset-0 bg-gradient-to-t from-black/55 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none" />
          <span className="absolute bottom-3 left-3 inline-flex items-center gap-1.5 rounded-full bg-black/55 backdrop-blur-md px-3 py-1.5 text-xs text-white opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
            <ZoomIn className="h-3.5 w-3.5" />
            Preview
          </span>
        </button>
        <div className="flex gap-2 p-3">
          <Button type="button" size="sm" variant="outline" onClick={() => setOpen(true)}>
            <Eye className="h-3.5 w-3.5" />
            View
          </Button>
          <Button type="button" size="sm" variant="secondary" disabled={busy} onClick={() => void onDownload()}>
            <Download className="h-3.5 w-3.5" />
            {busy ? "…" : "Download"}
          </Button>
        </div>
      </div>

      {open &&
        createPortal(
          <div
            className="fixed inset-0 z-[100] flex flex-col bg-black/85 backdrop-blur-sm"
            onClick={() => setOpen(false)}
            role="dialog"
            aria-modal
          >
            <div
              className="flex items-center justify-between gap-3 shrink-0 px-4 py-3 border-b border-white/10"
              onClick={(e) => e.stopPropagation()}
            >
              <p className="text-sm text-white/80 truncate">{filename}</p>
              <div className="flex gap-2">
                <Button size="sm" variant="secondary" disabled={busy} onClick={() => void onDownload()}>
                  <Download className="h-3.5 w-3.5" />
                  Download
                </Button>
                <Button size="sm" variant="ghost" className="text-white hover:bg-white/10" onClick={() => setOpen(false)}>
                  <X className="h-4 w-4" />
                </Button>
              </div>
            </div>
            <div
              className="flex-1 min-h-0 flex items-center justify-center p-4 sm:p-6"
              onClick={() => setOpen(false)}
            >
              <img
                src={src}
                alt=""
                onClick={(e) => e.stopPropagation()}
                className="max-w-full max-h-full w-auto h-auto object-contain rounded-xl shadow-2xl"
              />
            </div>
          </div>,
          document.body,
        )}
    </>
  )
}
