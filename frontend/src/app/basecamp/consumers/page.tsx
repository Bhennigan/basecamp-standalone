"use client"

import { useState } from "react"
import { useBaseCampConsumers, useBaseCampMappings, ConsumerCreate } from "@/hooks/use-basecamp"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { useToast } from "@/components/ui/use-toast"
import { CenteredSpinner } from "@/components/loading/spinner"
import { Plus, Trash2, Copy } from "lucide-react"

export default function ConsumersPage() {
  const { consumers, consumersLoading, createConsumer, deleteConsumer } = useBaseCampConsumers()
  const { mappings } = useBaseCampMappings()
  const { toast } = useToast()
  const [dialogOpen, setDialogOpen] = useState(false)
  const [formName, setFormName] = useState("")
  const [formDescription, setFormDescription] = useState("")
  const [formCallbackUrl, setFormCallbackUrl] = useState("")
  const [formMappingProfileId, setFormMappingProfileId] = useState("")

  const handleCreate = async () => {
    if (!formName.trim()) {
      toast({ title: "Error", description: "Name is required", variant: "destructive" })
      return
    }
    try {
      await createConsumer({
        name: formName,
        description: formDescription || null,
        callback_url: formCallbackUrl || null,
        mapping_profile_id: formMappingProfileId || null,
      })
      toast({ title: "Created", description: "Consumer registered" })
      setDialogOpen(false)
      setFormName("")
      setFormDescription("")
      setFormCallbackUrl("")
      setFormMappingProfileId("")
    } catch {
      toast({ title: "Error", description: "Failed to create consumer", variant: "destructive" })
    }
  }

  const handleDelete = async (id: string) => {
    try {
      await deleteConsumer(id)
      toast({ title: "Deleted", description: "Consumer unregistered" })
    } catch {
      toast({ title: "Error", description: "Failed to delete consumer", variant: "destructive" })
    }
  }

  const copyToClipboard = (text: string, label: string) => {
    navigator.clipboard.writeText(text)
    toast({ title: "Copied", description: `${label} copied to clipboard` })
  }

  const mappingMap = new Map((mappings || []).map(m => [m.id, m.name]))

  if (consumersLoading) return <CenteredSpinner />

  return (
    <div className="container py-8 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Consumers</h1>
          <p className="text-muted-foreground">Downstream engines that consume normalized data from Base Camp</p>
        </div>
        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogTrigger asChild>
            <Button><Plus className="mr-2 h-4 w-4" /> Register Consumer</Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Register Consumer</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 pt-4">
              <div>
                <Label>Name</Label>
                <Input value={formName} onChange={e => setFormName(e.target.value)} placeholder="e.g. ascension-prod" />
              </div>
              <div>
                <Label>Description</Label>
                <Input value={formDescription} onChange={e => setFormDescription(e.target.value)} placeholder="Optional description" />
              </div>
              <div>
                <Label>Webhook URL (optional)</Label>
                <Input value={formCallbackUrl} onChange={e => setFormCallbackUrl(e.target.value)} placeholder="https://..." />
                <p className="text-xs text-muted-foreground mt-1">Base Camp will POST new records to this URL on ingestion</p>
              </div>
              <div>
                <Label>Egress Mapping (optional)</Label>
                <Select value={formMappingProfileId} onValueChange={setFormMappingProfileId}>
                  <SelectTrigger><SelectValue placeholder="No transformation" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="">No transformation</SelectItem>
                    {(mappings || []).map(m => (
                      <SelectItem key={m.id} value={m.id}>{m.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground mt-1">Transform records to this consumer's preferred schema on output</p>
              </div>
              <Button onClick={handleCreate} className="w-full">Register</Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {!consumers?.length ? (
        <Card className="border-dashed">
          <CardContent className="flex flex-col items-center justify-center py-12 text-center">
            <p className="text-muted-foreground mb-4">No consumers registered. Register a downstream engine to start pulling data.</p>
            <Button variant="outline" onClick={() => setDialogOpen(true)}>Register First Consumer</Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {consumers.map(consumer => (
            <Card key={consumer.id}>
              <CardHeader className="flex flex-row items-start justify-between space-y-0">
                <div>
                  <CardTitle className="text-base">{consumer.name}</CardTitle>
                  {consumer.description && (
                    <p className="text-xs text-muted-foreground mt-1">{consumer.description}</p>
                  )}
                </div>
                <div className="flex gap-1">
                  <Button variant="ghost" size="icon" onClick={() => handleDelete(consumer.id)}>
                    <Trash2 className="h-4 w-4 text-destructive" />
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                <div className="space-y-3 text-sm">
                  <div className="flex justify-between items-center">
                    <span className="text-muted-foreground">Status</span>
                    <Badge variant={consumer.active ? "default" : "secondary"}>
                      {consumer.active ? "Active" : "Inactive"}
                    </Badge>
                  </div>
                  <div>
                    <span className="text-muted-foreground text-xs">API Key</span>
                    <div className="flex items-center gap-2 mt-1">
                      <code className="text-xs bg-muted px-2 py-1 rounded flex-1 truncate">{consumer.api_key}</code>
                      <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => copyToClipboard(consumer.api_key, "API key")}>
                        <Copy className="h-3 w-3" />
                      </Button>
                    </div>
                  </div>
                  {consumer.callback_url && (
                    <div className="flex justify-between items-center">
                      <span className="text-muted-foreground">Webhook</span>
                      <span className="text-xs font-mono truncate max-w-[150px]">{consumer.callback_url}</span>
                    </div>
                  )}
                  {consumer.mapping_profile_id && (
                    <div className="flex justify-between items-center">
                      <span className="text-muted-foreground">Egress Mapping</span>
                      <Badge variant="outline">{mappingMap.get(consumer.mapping_profile_id) || "Custom"}</Badge>
                    </div>
                  )}
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Subscriptions</span>
                    <Badge variant="outline">{consumer.schema_ids?.length || 0} schemas</Badge>
                  </div>
                  {consumer.last_poll && (
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Last Poll</span>
                      <span className="text-xs">{new Date(consumer.last_poll).toLocaleString()}</span>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Integration Documentation */}
      <div className="grid gap-4 md:grid-cols-2">
        <Card className="bg-muted/30">
          <CardContent className="py-4">
            <h3 className="font-medium mb-2">Pull (External API)</h3>
            <p className="text-sm text-muted-foreground mb-3">
              Downstream engines authenticate with their API key and poll for new data:
            </p>
            <div className="space-y-2">
              <code className="text-xs bg-background p-2 rounded block">
                GET /api/v1/feed?cursor=&#123;iso_timestamp&#125;&limit=100
              </code>
              <code className="text-xs bg-background p-2 rounded block">
                GET /api/v1/schemas
              </code>
              <code className="text-xs bg-background p-2 rounded block text-muted-foreground">
                Authorization: Bearer bc_xxxxxxx
              </code>
            </div>
          </CardContent>
        </Card>
        <Card className="bg-muted/30">
          <CardContent className="py-4">
            <h3 className="font-medium mb-2">Push (Webhooks)</h3>
            <p className="text-sm text-muted-foreground mb-3">
              If a webhook URL is set, Base Camp POSTs new records on ingestion:
            </p>
            <div className="space-y-2">
              <code className="text-xs bg-background p-2 rounded block">
                POST &#123;callback_url&#125;
              </code>
              <code className="text-xs bg-background p-2 rounded block text-muted-foreground">
                X-BaseCamp-Key: bc_xxxxxxx
              </code>
              <code className="text-xs bg-background p-2 rounded block text-muted-foreground">
                X-BaseCamp-Event: records.created
              </code>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
