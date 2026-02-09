"use client"

import { useState } from "react"
import {
  CheckCircle,
  Plug,
  Plus,
  RefreshCw,
  Trash2,
  XCircle,
  Zap,
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
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import { useToast } from "@/components/ui/use-toast"
import { useBaseCampConnectors } from "@/hooks/use-basecamp"

const CONNECTOR_TYPES = [
  { value: "sherlock", label: "Sherlock", description: "Username search across social networks" },
  { value: "harvester", label: "TheHarvester", description: "Email, domain, and subdomain OSINT" },
  { value: "shodan", label: "Shodan", description: "Internet-connected device search engine" },
  { value: "zerofox", label: "ZeroFox", description: "Digital risk protection platform" },
]

function ConnectorCard({
  connector,
  onTest,
  onDelete,
  testPending,
}: {
  connector: { name: string; type: string; status: string; health?: string }
  onTest: () => void
  onDelete: () => void
  testPending: boolean
}) {
  const info = CONNECTOR_TYPES.find((t) => t.value === connector.type)
  const isHealthy = connector.health === "healthy" || connector.status === "connected"

  return (
    <Card className="border-border/50">
      <CardContent className="flex items-center justify-between p-4">
        <div className="flex items-center gap-4">
          <div className="flex size-10 items-center justify-center rounded-lg bg-muted">
            <Plug className="size-5 text-muted-foreground" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-medium">{connector.name}</span>
              <Badge variant="secondary" className="text-xs capitalize">{connector.type}</Badge>
              {isHealthy ? (
                <Badge variant="default" className="gap-1 text-xs">
                  <CheckCircle className="size-3" /> Online
                </Badge>
              ) : (
                <Badge variant="outline" className="gap-1 text-xs">
                  <XCircle className="size-3" /> Offline
                </Badge>
              )}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              {info?.description || connector.type}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={onTest}
            disabled={testPending}
            className="gap-1"
          >
            <Zap className="size-3" /> Test
          </Button>
          <Button variant="ghost" size="sm" onClick={onDelete}>
            <Trash2 className="size-4 text-destructive" />
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

export default function ConnectorsPage() {
  const { toast } = useToast()
  const [showCreate, setShowCreate] = useState(false)
  const [newName, setNewName] = useState("")
  const [newType, setNewType] = useState("")
  const [newConfig, setNewConfig] = useState("{}")

  const {
    connectors,
    connectorsLoading,
    refetchConnectors,
    createConnector,
    createConnectorPending,
    deleteConnector,
    testConnector,
    testConnectorPending,
  } = useBaseCampConnectors()

  const handleCreate = async () => {
    if (!newName || !newType) return
    try {
      let config = {}
      try { config = JSON.parse(newConfig) } catch { /* keep empty */ }
      await createConnector({ name: newName, type: newType, config })
      toast({ title: "Connector registered", description: `${newName} (${newType}) created` })
      setShowCreate(false)
      setNewName("")
      setNewType("")
      setNewConfig("{}")
    } catch (err: any) {
      toast({ title: "Error", description: err.message, variant: "destructive" })
    }
  }

  const handleTest = async (name: string) => {
    try {
      const result = await testConnector({ name })
      toast({ title: "Test result", description: JSON.stringify(result).slice(0, 200) })
    } catch (err: any) {
      toast({ title: "Test failed", description: err.message, variant: "destructive" })
    }
  }

  const handleDelete = async (name: string) => {
    try {
      await deleteConnector(name)
      toast({ title: "Connector removed", description: `${name} deleted` })
    } catch (err: any) {
      toast({ title: "Error", description: err.message, variant: "destructive" })
    }
  }

  if (connectorsLoading) return <CenteredSpinner />

  return (
    <div className="size-full overflow-auto">
      <div className="container flex h-full flex-col space-y-6 py-8">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Connectors</h1>
            <p className="text-muted-foreground">Manage OSINT connector integrations</p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={() => refetchConnectors()} className="gap-2">
              <RefreshCw className="size-4" /> Refresh
            </Button>
            <Button size="sm" onClick={() => setShowCreate(true)} className="gap-2">
              <Plus className="size-4" /> Register Connector
            </Button>
          </div>
        </div>

        {/* Connector types overview */}
        <div className="grid gap-3 md:grid-cols-4">
          {CONNECTOR_TYPES.map((ct) => (
            <Card key={ct.value} className="border-border/50">
              <CardContent className="p-4">
                <div className="font-medium text-sm">{ct.label}</div>
                <div className="text-xs text-muted-foreground mt-1">{ct.description}</div>
              </CardContent>
            </Card>
          ))}
        </div>

        {/* Registered connectors */}
        <div>
          <h2 className="text-lg font-semibold mb-3">Registered Connectors</h2>
          {(!connectors || connectors.length === 0) ? (
            <Card className="border-border/50">
              <CardContent className="flex h-32 items-center justify-center text-muted-foreground">
                No connectors registered yet. Click "Register Connector" to add one.
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-3">
              {connectors.map((c) => (
                <ConnectorCard
                  key={c.name}
                  connector={c}
                  onTest={() => handleTest(c.name)}
                  onDelete={() => handleDelete(c.name)}
                  testPending={testConnectorPending}
                />
              ))}
            </div>
          )}
        </div>

        {/* Create dialog */}
        <Dialog open={showCreate} onOpenChange={setShowCreate}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Register Connector</DialogTitle>
              <DialogDescription>Add a new OSINT connector integration</DialogDescription>
            </DialogHeader>
            <div className="space-y-4">
              <div>
                <Label>Name</Label>
                <Input
                  placeholder="my-sherlock"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                />
              </div>
              <div>
                <Label>Type</Label>
                <Select value={newType} onValueChange={setNewType}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select connector type" />
                  </SelectTrigger>
                  <SelectContent>
                    {CONNECTOR_TYPES.map((ct) => (
                      <SelectItem key={ct.value} value={ct.value}>{ct.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label>Configuration (JSON)</Label>
                <Textarea
                  value={newConfig}
                  onChange={(e) => setNewConfig(e.target.value)}
                  rows={4}
                  className="font-mono text-sm"
                />
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setShowCreate(false)}>Cancel</Button>
              <Button onClick={handleCreate} disabled={createConnectorPending || !newName || !newType}>
                {createConnectorPending ? "Creating..." : "Register"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </div>
  )
}
