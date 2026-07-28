import {
  useLinkedInStatusQuery,
  useLinkedInConnectMutation,
} from "@/features/api/contentApi"
import { Button } from "@/components/ui/button"

export function LinkedInPage() {
  const { data, refetch } = useLinkedInStatusQuery()
  const [connect, state] = useLinkedInConnectMutation()

  const start = async () => {
    const res = await connect().unwrap()
    window.location.href = res.authorizeUrl
  }

  return (
    <div className="space-y-6 max-w-lg">
      <div>
        <h1 className="font-display text-3xl">LinkedIn</h1>
        <p className="text-sm text-muted-foreground">
          Connect the company LinkedIn account used for publishing approved posts.
        </p>
      </div>
      <div className="rounded-2xl border border-border p-6 space-y-3 bg-background/40">
        <p className="text-sm">
          Status:{" "}
          <strong>{data?.connected ? `Connected (${data.username || "user"})` : "Not connected"}</strong>
        </p>
        <div className="flex gap-2">
          <Button onClick={() => void start()} disabled={state.isLoading}>
            Connect LinkedIn
          </Button>
          <Button variant="outline" onClick={() => void refetch()}>
            Refresh
          </Button>
        </div>
      </div>
    </div>
  )
}
