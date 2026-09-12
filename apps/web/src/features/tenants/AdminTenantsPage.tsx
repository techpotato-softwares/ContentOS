import { useState } from "react"
import { Link } from "react-router-dom"
import { useListTenantsQuery, useCreateTenantMutation } from "@/features/api/contentApi"
import { Button } from "@/components/ui/button"
import { Input, Label } from "@/components/ui/input"

export function AdminTenantsPage() {
  const { data: tenants = [], isLoading } = useListTenantsQuery()
  const [create, createState] = useCreateTenantMutation()
  const [name, setName] = useState("")

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-2xl md:text-3xl">Tenants</h1>
        <p className="text-sm text-muted-foreground">Super admin — manage client companies and training.</p>
      </div>
      <form
        className="flex flex-col sm:flex-row gap-2 sm:items-end"
        onSubmit={(e) => {
          e.preventDefault()
          void create({ name }).then(() => setName(""))
        }}
      >
        <div className="flex-1 space-y-1 w-full">
          <Label>New company</Label>
          <Input value={name} onChange={(e) => setName(e.target.value)} required />
        </div>
        <Button type="submit" className="w-full sm:w-auto" disabled={createState.isLoading}>
          Create
        </Button>
      </form>
      {isLoading && <p>Loading…</p>}
      <ul className="space-y-2">
        {tenants.map((t) => (
          <li
            key={t.tenantId}
            className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 rounded-xl border border-border px-4 py-3 bg-background/40"
          >
            <div>
              <div className="font-medium">{t.name}</div>
              <div className="text-xs text-muted-foreground">
                {t.slug} · UI {t.uiMode}
              </div>
            </div>
            <Button asChild variant="outline" size="sm">
              <Link to={`/admin/tenants/${t.tenantId}/training`}>Training</Link>
            </Button>
          </li>
        ))}
      </ul>
    </div>
  )
}
