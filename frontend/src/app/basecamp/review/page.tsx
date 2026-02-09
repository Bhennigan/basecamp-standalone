"use client"

import { useState } from "react"
import {
  CheckCircle,
  Clock,
  Eye,
  RefreshCw,
  ShieldAlert,
  ThumbsDown,
  ThumbsUp,
  XCircle,
} from "lucide-react"
import { CenteredSpinner } from "@/components/loading/spinner"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Textarea } from "@/components/ui/textarea"
import { useToast } from "@/components/ui/use-toast"
import {
  useBaseCampReviewQueue,
  type BaseCampReviewItem,
} from "@/hooks/use-basecamp"

function priorityBadge(priority: string) {
  const map: Record<string, "destructive" | "secondary" | "outline" | "default"> = {
    critical: "destructive",
    high: "destructive",
    medium: "secondary",
    low: "outline",
  }
  return <Badge variant={map[priority] || "outline"} className="capitalize">{priority}</Badge>
}

function statusBadge(status: string) {
  const map: Record<string, { variant: "default" | "secondary" | "destructive" | "outline"; icon: React.ReactNode }> = {
    pending: { variant: "outline", icon: <Clock className="mr-1 size-3" /> },
    in_review: { variant: "secondary", icon: <Eye className="mr-1 size-3" /> },
    approved: { variant: "default", icon: <CheckCircle className="mr-1 size-3" /> },
    rejected: { variant: "destructive", icon: <XCircle className="mr-1 size-3" /> },
    reclassified: { variant: "secondary", icon: <ShieldAlert className="mr-1 size-3" /> },
  }
  const cfg = map[status] || { variant: "outline" as const, icon: null }
  return <Badge variant={cfg.variant} className="capitalize">{cfg.icon}{status.replace("_", " ")}</Badge>
}

function StatCard({
  label,
  value,
  icon: Icon,
}: {
  label: string
  value: number
  icon: React.ComponentType<{ className?: string }>
}) {
  return (
    <Card className="border-border/50">
      <CardContent className="flex items-center gap-3 p-4">
        <Icon className="size-5 text-muted-foreground" />
        <div>
          <div className="text-xl font-bold">{value}</div>
          <div className="text-xs text-muted-foreground">{label}</div>
        </div>
      </CardContent>
    </Card>
  )
}

export default function ReviewPage() {
  const { toast } = useToast()
  const [selectedItem, setSelectedItem] = useState<BaseCampReviewItem | null>(null)
  const [notes, setNotes] = useState("")

  const {
    reviewItems,
    reviewLoading,
    refetchReview,
    reviewStats,
    statsLoading,
    refetchStats,
    submitDecision,
    decisionPending,
  } = useBaseCampReviewQueue()

  const handleDecision = async (decision: "approved" | "rejected") => {
    if (!selectedItem) return
    try {
      await submitDecision({
        itemId: selectedItem.id,
        decision,
        reviewer_id: "default-reviewer",
        notes: notes || undefined,
      })
      toast({
        title: decision === "approved" ? "Approved" : "Rejected",
        description: `Item ${selectedItem.id.slice(0, 8)} ${decision}`,
      })
      setSelectedItem(null)
      setNotes("")
      refetchReview()
      refetchStats()
    } catch (err: any) {
      toast({ title: "Error", description: err.message, variant: "destructive" })
    }
  }

  if (reviewLoading && !reviewItems.length) return <CenteredSpinner />

  return (
    <div className="size-full overflow-auto">
      <div className="container flex h-full flex-col space-y-6 py-8">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Review Queue</h1>
            <p className="text-muted-foreground">Human-in-the-loop review for low-confidence items</p>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => { refetchReview(); refetchStats(); }}
            className="gap-2"
          >
            <RefreshCw className="size-4" /> Refresh
          </Button>
        </div>

        {/* Stats */}
        {reviewStats && (
          <div className="grid gap-4 md:grid-cols-5">
            <StatCard label="Pending" value={reviewStats.pending ?? 0} icon={Clock} />
            <StatCard label="In Review" value={reviewStats.in_review ?? 0} icon={Eye} />
            <StatCard label="Approved" value={reviewStats.approved ?? 0} icon={CheckCircle} />
            <StatCard label="Rejected" value={reviewStats.rejected ?? 0} icon={XCircle} />
            <StatCard label="Total" value={reviewStats.total ?? 0} icon={ShieldAlert} />
          </div>
        )}

        {/* Queue */}
        <Card className="border-border/50">
          <CardHeader>
            <CardTitle>Pending Items</CardTitle>
            <CardDescription>Items requiring human review</CardDescription>
          </CardHeader>
          <CardContent>
            {reviewItems.length === 0 ? (
              <div className="flex h-32 items-center justify-center text-muted-foreground">
                No items in the review queue
              </div>
            ) : (
              <div className="space-y-3">
                {reviewItems.map((item) => (
                  <div
                    key={item.id}
                    className="flex items-center justify-between rounded-lg border border-border/50 bg-muted/20 p-4 hover:bg-muted/40 transition-colors cursor-pointer"
                    onClick={() => { setSelectedItem(item); setNotes(""); }}
                  >
                    <div className="flex flex-col gap-1">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium font-mono">
                          {(item.data?.value as string) || item.id.slice(0, 12)}
                        </span>
                        <Badge variant="secondary" className="text-xs capitalize">
                          {item.item_type.replace("_", " ")}
                        </Badge>
                        {priorityBadge(item.priority)}
                      </div>
                      <span className="text-xs text-muted-foreground">
                        {item.reason || `Confidence: ${(item.confidence_score * 100).toFixed(0)}%`}
                      </span>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-xs text-muted-foreground">
                        {new Date(item.created_at).toLocaleDateString()}
                      </span>
                      {statusBadge(item.status)}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Decision dialog */}
        <Dialog open={!!selectedItem} onOpenChange={(open) => !open && setSelectedItem(null)}>
          <DialogContent className="max-w-lg">
            <DialogHeader>
              <DialogTitle>Review Item</DialogTitle>
              <DialogDescription>Review and approve or reject this item</DialogDescription>
            </DialogHeader>
            {selectedItem && (
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div>
                    <span className="text-muted-foreground">Type: </span>
                    <Badge variant="secondary" className="capitalize">
                      {selectedItem.item_type.replace("_", " ")}
                    </Badge>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Priority: </span>
                    {priorityBadge(selectedItem.priority)}
                  </div>
                  <div>
                    <span className="text-muted-foreground">Confidence: </span>
                    <span className="font-mono">
                      {(selectedItem.confidence_score * 100).toFixed(1)}%
                    </span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Status: </span>
                    {statusBadge(selectedItem.status)}
                  </div>
                </div>
                {selectedItem.reason && (
                  <div className="text-sm">
                    <span className="text-muted-foreground">Reason: </span>
                    <span>{selectedItem.reason}</span>
                  </div>
                )}
                {selectedItem.data && Object.keys(selectedItem.data).length > 0 && (
                  <div>
                    <span className="text-sm text-muted-foreground">Data:</span>
                    <pre className="mt-1 rounded bg-muted/50 p-3 text-xs overflow-auto max-h-40">
                      {JSON.stringify(selectedItem.data, null, 2)}
                    </pre>
                  </div>
                )}
                <div>
                  <span className="text-sm text-muted-foreground">Review Notes</span>
                  <Textarea
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                    placeholder="Optional notes about this decision..."
                    rows={3}
                    className="mt-1"
                  />
                </div>
              </div>
            )}
            <DialogFooter className="gap-2">
              <Button
                variant="destructive"
                onClick={() => handleDecision("rejected")}
                disabled={decisionPending}
                className="gap-2"
              >
                <ThumbsDown className="size-4" /> Reject
              </Button>
              <Button
                onClick={() => handleDecision("approved")}
                disabled={decisionPending}
                className="gap-2"
              >
                <ThumbsUp className="size-4" /> Approve
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </div>
  )
}
