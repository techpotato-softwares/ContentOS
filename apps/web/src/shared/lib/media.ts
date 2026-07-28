/** Normalize stored image URLs for same-origin view/download via Vite /media proxy. */
export function mediaSrc(url?: string | null): string | undefined {
  if (!url) return undefined
  try {
    if (url.startsWith("/media/")) return url
    const u = new URL(url, window.location.origin)
    if (u.pathname.startsWith("/media/")) return u.pathname
  } catch {
    /* keep original */
  }
  return url
}

export async function downloadMedia(url: string, filename: string) {
  const src = mediaSrc(url) || url
  const res = await fetch(src)
  if (!res.ok) throw new Error(`Download failed (${res.status})`)
  const blob = await res.blob()
  const objectUrl = URL.createObjectURL(blob)
  const a = document.createElement("a")
  a.href = objectUrl
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(objectUrl)
}
