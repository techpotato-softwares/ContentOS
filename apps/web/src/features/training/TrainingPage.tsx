import { useEffect, useState } from "react"
import { useParams } from "react-router-dom"
import {
  useGetTrainingQuery,
  usePutTrainingMutation,
  useLazyPreviewTrainingQuery,
  useUploadLogoMutation,
  useDeleteLogoMutation,
} from "@/features/api/contentApi"
import { emptyTraining, type TenantTrainingSchema } from "@/shared/types/training"
import { Button } from "@/components/ui/button"
import { Input, Label, Textarea } from "@/components/ui/input"
import { mediaSrc } from "@/shared/lib/media"

function csv(v: string) {
  return v
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean)
}

function fileToBase64(file: File): Promise<{ base64: string; contentType: string }> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      const result = String(reader.result || "")
      const base64 = result.includes(",") ? result.split(",", 1)[1] : result
      resolve({ base64, contentType: file.type || "image/png" })
    }
    reader.onerror = () => reject(reader.error)
    reader.readAsDataURL(file)
  })
}

export function TrainingPage({ adminTenantId }: { adminTenantId?: number }) {
  const params = useParams()
  const tenantId = adminTenantId ?? (params.id ? Number(params.id) : undefined)
  const { data, isLoading } = useGetTrainingQuery(tenantId)
  const [put, putState] = usePutTrainingMutation()
  const [preview, previewState] = useLazyPreviewTrainingQuery()
  const [uploadLogo, uploadState] = useUploadLogoMutation()
  const [deleteLogo, deleteState] = useDeleteLogoMutation()
  const [form, setForm] = useState<TenantTrainingSchema>(emptyTraining())
  const [pack, setPack] = useState("")
  const [logoMsg, setLogoMsg] = useState<string | null>(null)

  useEffect(() => {
    if (data) {
      const base = emptyTraining()
      setForm({
        ...base,
        ...data,
        company: { ...base.company, ...data.company },
        audience: { ...base.audience, ...data.audience },
        messaging: { ...base.messaging, ...data.messaging },
        brand_visual: { ...base.brand_visual, ...data.brand_visual },
      })
    }
  }, [data])

  const save = async () => {
    await put({ tenantId, body: form }).unwrap()
  }

  const loadPreview = async () => {
    if (!tenantId) return
    const res = await preview(tenantId).unwrap()
    setPack(res.contextPack)
  }

  const onLogoFile = async (file: File | null) => {
    if (!file) return
    setLogoMsg(null)
    if (file.size > 2 * 1024 * 1024) {
      setLogoMsg("Logo must be under 2MB")
      return
    }
    try {
      const { base64, contentType } = await fileToBase64(file)
      const res = await uploadLogo({
        imageBase64: base64,
        contentType,
        filename: file.name,
        tenantId,
      }).unwrap()
      setForm((f) => ({
        ...f,
        brand_visual: { ...f.brand_visual, logo_url: res.logoUrl },
      }))
      setLogoMsg("Logo uploaded — it will appear on generated posts.")
    } catch {
      setLogoMsg("Logo upload failed")
    }
  }

  const onClearLogo = async () => {
    await deleteLogo(tenantId).unwrap()
    setForm((f) => ({ ...f, brand_visual: { ...f.brand_visual, logo_url: "" } }))
    setLogoMsg("Logo removed")
  }

  if (isLoading) return <p>Loading training…</p>

  const logoPreview = mediaSrc(form.brand_visual.logo_url) || form.brand_visual.logo_url

  return (
    <div className="space-y-8 max-w-4xl">
      <div>
        <h1 className="font-display text-2xl md:text-3xl">Company training</h1>
        <p className="text-sm text-muted-foreground">
          Structured company records for consistent generation — not a topic allowlist.
        </p>
      </div>

      <section className="space-y-3">
        <h2 className="font-display text-xl">Company</h2>
        <div className="grid md:grid-cols-2 gap-3">
          <Field label="Legal name" value={form.company.legal_name} onChange={(v) => setForm({ ...form, company: { ...form.company, legal_name: v } })} />
          <Field label="Display name" value={form.company.display_name} onChange={(v) => setForm({ ...form, company: { ...form.company, display_name: v } })} />
          <Field label="Industry / domain" value={form.company.industry} onChange={(v) => setForm({ ...form, company: { ...form.company, industry: v } })} />
          <Field label="Website" value={form.company.website} onChange={(v) => setForm({ ...form, company: { ...form.company, website: v } })} />
          <Field label="Phone" value={form.company.phone || ""} onChange={(v) => setForm({ ...form, company: { ...form.company, phone: v } })} />
          <Field label="Email" value={form.company.email || ""} onChange={(v) => setForm({ ...form, company: { ...form.company, email: v } })} />
          <div className="md:col-span-2 space-y-1">
            <Label>One-liner</Label>
            <Input
              maxLength={160}
              value={form.company.one_liner}
              onChange={(e) =>
                setForm({ ...form, company: { ...form.company, one_liner: e.target.value } })
              }
            />
          </div>
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="font-display text-xl">Messaging</h2>
        <Field
          label="Tone (comma-separated)"
          value={form.messaging.tone.join(", ")}
          onChange={(v) => setForm({ ...form, messaging: { ...form.messaging, tone: csv(v) } })}
        />
        <Field
          label="Voice dos"
          value={form.messaging.voice_dos.join(", ")}
          onChange={(v) => setForm({ ...form, messaging: { ...form.messaging, voice_dos: csv(v) } })}
        />
        <Field
          label="Voice don'ts"
          value={form.messaging.voice_donts.join(", ")}
          onChange={(v) =>
            setForm({ ...form, messaging: { ...form.messaging, voice_donts: csv(v) } })
          }
        />
        <Field
          label="Banned claims (comma-separated)"
          value={form.messaging.banned_claims.join(", ")}
          onChange={(v) =>
            setForm({ ...form, messaging: { ...form.messaging, banned_claims: csv(v) } })
          }
        />
        <div className="space-y-1">
          <Label>Approved facts (one per line)</Label>
          <Textarea
            value={form.approved_facts.join("\n")}
            onChange={(e) =>
              setForm({
                ...form,
                approved_facts: e.target.value.split("\n").map((s) => s.trim()).filter(Boolean),
              })
            }
          />
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="font-display text-xl">Brand / UI theme</h2>
        <p className="text-xs text-muted-foreground">
          Upload a logo to composite onto LinkedIn posts. White-label UI applies only when logo + all three
          colors are set and ui_mode is white_label.
        </p>
        <div className="rounded-2xl border border-border p-4 space-y-3 bg-background/40">
          <Label>Company logo</Label>
          <div className="flex flex-wrap items-center gap-4">
            {logoPreview ? (
              <img
                src={logoPreview}
                alt="Logo preview"
                className="h-16 w-16 rounded-xl object-contain border border-border bg-muted"
              />
            ) : (
              <div className="h-16 w-16 rounded-xl border border-dashed border-border flex items-center justify-center text-xs text-muted-foreground">
                No logo
              </div>
            )}
            <div className="space-y-2">
              <Input
                type="file"
                accept="image/png,image/jpeg,image/webp"
                disabled={uploadState.isLoading}
                onChange={(e) => void onLogoFile(e.target.files?.[0] || null)}
              />
              <div className="flex gap-2">
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  disabled={!form.brand_visual.logo_url || deleteState.isLoading}
                  onClick={() => void onClearLogo()}
                >
                  Remove logo
                </Button>
              </div>
            </div>
          </div>
          {logoMsg && <p className="text-xs text-muted-foreground">{logoMsg}</p>}
        </div>
        <div className="grid md:grid-cols-2 gap-3">
          <Field
            label="Primary color"
            value={form.brand_visual.primary_color}
            onChange={(v) =>
              setForm({ ...form, brand_visual: { ...form.brand_visual, primary_color: v } })
            }
          />
          <Field
            label="Secondary color"
            value={form.brand_visual.secondary_color}
            onChange={(v) =>
              setForm({ ...form, brand_visual: { ...form.brand_visual, secondary_color: v } })
            }
          />
          <Field
            label="Accent color"
            value={form.brand_visual.accent_color}
            onChange={(v) =>
              setForm({ ...form, brand_visual: { ...form.brand_visual, accent_color: v } })
            }
          />
          <Field
            label="App display name"
            value={form.brand_visual.app_display_name}
            onChange={(v) =>
              setForm({ ...form, brand_visual: { ...form.brand_visual, app_display_name: v } })
            }
          />
          <Field
            label="Visual style keywords"
            value={form.brand_visual.visual_style_keywords.join(", ")}
            onChange={(v) =>
              setForm({
                ...form,
                brand_visual: { ...form.brand_visual, visual_style_keywords: csv(v) },
              })
            }
          />
          <Field
            label="Image do-nots"
            value={form.brand_visual.image_do_nots.join(", ")}
            onChange={(v) =>
              setForm({
                ...form,
                brand_visual: { ...form.brand_visual, image_do_nots: csv(v) },
              })
            }
          />
          <div className="space-y-1">
            <Label>UI mode</Label>
            <select
              className="h-10 w-full rounded-xl border border-border bg-background/60 px-3 text-sm"
              value={form.brand_visual.ui_mode}
              onChange={(e) =>
                setForm({
                  ...form,
                  brand_visual: {
                    ...form.brand_visual,
                    ui_mode: e.target.value as "platform" | "white_label",
                  },
                })
              }
            >
              <option value="platform">platform (default)</option>
              <option value="white_label">white_label</option>
            </select>
          </div>
        </div>
      </section>

      <div className="flex flex-col sm:flex-row gap-2">
        <Button className="w-full sm:w-auto" onClick={() => void save()} disabled={putState.isLoading}>
          Save training
        </Button>
        {tenantId ? (
          <Button
            variant="outline"
            className="w-full sm:w-auto"
            onClick={() => void loadPreview()}
            disabled={previewState.isLoading}
          >
            Preview context pack
          </Button>
        ) : null}
      </div>
      {pack && (
        <pre className="text-xs whitespace-pre-wrap rounded-2xl border border-border p-4 bg-muted/40 max-h-80 overflow-auto">
          {pack}
        </pre>
      )}
    </div>
  )
}

function Field({
  label,
  value,
  onChange,
}: {
  label: string
  value: string
  onChange: (v: string) => void
}) {
  return (
    <div className="space-y-1">
      <Label>{label}</Label>
      <Input value={value} onChange={(e) => onChange(e.target.value)} />
    </div>
  )
}
