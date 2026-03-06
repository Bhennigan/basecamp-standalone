"use client"

import { useState, useMemo } from "react"
import { useRouter } from "next/navigation"
import { useBaseCampMappings, useBaseCampSchemas, MappingProfileCreate, FieldMapping } from "@/hooks/use-basecamp"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { useToast } from "@/components/ui/use-toast"
import { CenteredSpinner } from "@/components/loading/spinner"
import { Plus, Trash2, ArrowRight, GripVertical } from "lucide-react"

const TRANSFORM_TYPES = [
  "rename", "cast", "format", "extract", "default", "concat",
  "split", "lookup", "lower", "upper", "trim", "regex",
] as const

export default function MappingsPage() {
  const { mappings, mappingsLoading, createMapping, deleteMapping } = useBaseCampMappings()
  const { schemas } = useBaseCampSchemas()
  const { toast } = useToast()
  const [dialogOpen, setDialogOpen] = useState(false)

  const [formName, setFormName] = useState("")
  const [formDescription, setFormDescription] = useState("")
  const [formTargetSchema, setFormTargetSchema] = useState("")
  const [formDropUnmapped, setFormDropUnmapped] = useState(false)
  const [formMappings, setFormMappings] = useState<FieldMapping[]>([
    { source_field: "", target_field: "", transform: "rename", params: {} },
  ])

  const resetForm = () => {
    setFormName("")
    setFormDescription("")
    setFormTargetSchema("")
    setFormDropUnmapped(false)
    setFormMappings([{ source_field: "", target_field: "", transform: "rename", params: {} }])
  }

  const handleCreate = async () => {
    if (!formName.trim() || !formTargetSchema) {
      toast({ title: "Error", description: "Name and target schema are required", variant: "destructive" })
      return
    }
    try {
      await createMapping({
        name: formName,
        description: formDescription || null,
        target_schema_id: formTargetSchema,
        mappings: formMappings.filter(m => m.source_field && m.target_field),
        drop_unmapped: formDropUnmapped,
      })
      toast({ title: "Created", description: "Mapping profile created" })
      setDialogOpen(false)
      resetForm()
    } catch {
      toast({ title: "Error", description: "Failed to create mapping", variant: "destructive" })
    }
  }

  const handleDelete = async (id: string) => {
    try {
      await deleteMapping(id)
      toast({ title: "Deleted", description: "Mapping profile deleted" })
    } catch {
      toast({ title: "Error", description: "Failed to delete mapping", variant: "destructive" })
    }
  }

  const addMappingRow = () => {
    setFormMappings([...formMappings, { source_field: "", target_field: "", transform: "rename", params: {} }])
  }

  const updateMappingRow = (index: number, field: keyof FieldMapping, value: any) => {
    const updated = [...formMappings]
    updated[index] = { ...updated[index], [field]: value }
    setFormMappings(updated)
  }

  const removeMappingRow = (index: number) => {
    setFormMappings(formMappings.filter((_, i) => i !== index))
  }

  if (mappingsLoading) return <CenteredSpinner />

  const schemaMap = new Map((schemas || []).map(s => [s.id, s.name]))

  return (
    <div className="container py-8 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Mapping Profiles</h1>
          <p className="text-muted-foreground">Transform and normalize data between schemas</p>
        </div>
        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogTrigger asChild>
            <Button onClick={resetForm}><Plus className="mr-2 h-4 w-4" /> New Mapping</Button>
          </DialogTrigger>
          <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>Create Mapping Profile</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 pt-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label>Name</Label>
                  <Input value={formName} onChange={e => setFormName(e.target.value)} placeholder="e.g. Netcraft to Threats" />
                </div>
                <div>
                  <Label>Target Schema</Label>
                  <Select value={formTargetSchema} onValueChange={setFormTargetSchema}>
                    <SelectTrigger><SelectValue placeholder="Select schema" /></SelectTrigger>
                    <SelectContent>
                      {(schemas || []).map(s => (
                        <SelectItem key={s.id} value={s.id}>{s.name}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div>
                <Label>Description</Label>
                <Input value={formDescription} onChange={e => setFormDescription(e.target.value)} placeholder="Optional description" />
              </div>

              <div>
                <div className="flex items-center justify-between mb-2">
                  <Label>Field Mappings</Label>
                  <Button variant="outline" size="sm" onClick={addMappingRow}><Plus className="mr-1 h-3 w-3" /> Add Field</Button>
                </div>
                <div className="space-y-2">
                  {formMappings.map((m, i) => (
                    <div key={i} className="flex items-center gap-2 p-2 border rounded-md bg-muted/30">
                      <Input
                        className="flex-1"
                        placeholder="source_field"
                        value={m.source_field}
                        onChange={e => updateMappingRow(i, "source_field", e.target.value)}
                      />
                      <ArrowRight className="h-4 w-4 text-muted-foreground shrink-0" />
                      <Input
                        className="flex-1"
                        placeholder="target_field"
                        value={m.target_field}
                        onChange={e => updateMappingRow(i, "target_field", e.target.value)}
                      />
                      <Select value={m.transform} onValueChange={v => updateMappingRow(i, "transform", v)}>
                        <SelectTrigger className="w-28"><SelectValue /></SelectTrigger>
                        <SelectContent>
                          {TRANSFORM_TYPES.map(t => (
                            <SelectItem key={t} value={t}>{t}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <Button variant="ghost" size="icon" onClick={() => removeMappingRow(i)}>
                        <Trash2 className="h-4 w-4 text-destructive" />
                      </Button>
                    </div>
                  ))}
                </div>
              </div>

              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={formDropUnmapped}
                  onChange={e => setFormDropUnmapped(e.target.checked)}
                  className="rounded"
                />
                <Label>Drop unmapped fields</Label>
              </div>

              <Button onClick={handleCreate} className="w-full">Create Profile</Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {!mappings?.length ? (
        <Card className="border-dashed">
          <CardContent className="flex flex-col items-center justify-center py-12 text-center">
            <p className="text-muted-foreground mb-4">No mapping profiles yet. Create one to start transforming data.</p>
            <Button variant="outline" onClick={() => setDialogOpen(true)}>Create First Mapping</Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {mappings.map(profile => (
            <Card key={profile.id}>
              <CardHeader className="flex flex-row items-start justify-between space-y-0">
                <div>
                  <CardTitle className="text-base">{profile.name}</CardTitle>
                  {profile.description && (
                    <p className="text-xs text-muted-foreground mt-1">{profile.description}</p>
                  )}
                </div>
                <Button variant="ghost" size="icon" onClick={() => handleDelete(profile.id)}>
                  <Trash2 className="h-4 w-4 text-destructive" />
                </Button>
              </CardHeader>
              <CardContent>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Target Schema</span>
                    <span className="font-mono text-xs">{schemaMap.get(profile.target_schema_id) || profile.target_schema_id.slice(0, 8)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Fields</span>
                    <Badge variant="secondary">{profile.mappings?.length || 0} mappings</Badge>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Drop Unmapped</span>
                    <Badge variant={profile.drop_unmapped ? "default" : "outline"}>
                      {profile.drop_unmapped ? "Yes" : "No"}
                    </Badge>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
