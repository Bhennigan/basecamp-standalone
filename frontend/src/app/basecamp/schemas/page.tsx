"use client"

import { useEffect, useState } from "react"
import {
  ChevronDown,
  ChevronRight,
  Layers,
  MoreHorizontal,
  Pencil,
  Plus,
  Trash2,
  X,
} from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
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
import { CenteredSpinner } from "@/components/loading/spinner"
import {
  useBaseCampSchemas,
  type BaseCampSchema,
} from "@/hooks/use-basecamp"

const FIELD_TYPES = [
  "str",
  "int",
  "float",
  "bool",
  "datetime",
  "json",
  "list",
  "dict",
] as const

type FieldType = (typeof FIELD_TYPES)[number]

interface SchemaFormField {
  name: string
  type: FieldType
  required: boolean
  description?: string
}

interface SchemaFormData {
  name: string
  description: string
  fields: SchemaFormField[]
}

const initialFormData: SchemaFormData = {
  name: "",
  description: "",
  fields: [],
}

function getSchemaStatus(schema: BaseCampSchema): "DRAFT" | "ACTIVE" | "DEPRECATED" {
  // Determine status based on schema properties
  // For now, we'll use a simple heuristic based on fields
  if (schema.fields.length === 0) {
    return "DRAFT"
  }
  // Check if schema has been updated recently (within last 30 days)
  const updatedAt = new Date(schema.updated_at)
  const thirtyDaysAgo = new Date()
  thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30)

  if (updatedAt < thirtyDaysAgo) {
    return "DEPRECATED"
  }
  return "ACTIVE"
}

function StatusBadge({ status }: { status: "DRAFT" | "ACTIVE" | "DEPRECATED" }) {
  const variants: Record<
    string,
    { className: string; label: string }
  > = {
    DRAFT: {
      className: "bg-yellow-500/20 text-yellow-400 hover:bg-yellow-500/30",
      label: "Draft",
    },
    ACTIVE: {
      className: "bg-green-500/20 text-green-400 hover:bg-green-500/30",
      label: "Active",
    },
    DEPRECATED: {
      className: "bg-gray-500/20 text-gray-400 hover:bg-gray-500/30",
      label: "Deprecated",
    },
  }

  const { className, label } = variants[status]

  return (
    <Badge variant="outline" className={className}>
      {label}
    </Badge>
  )
}

function formatDate(dateString: string): string {
  const date = new Date(dateString)
  return date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  })
}

function FieldEditor({
  field,
  index,
  onUpdate,
  onRemove,
}: {
  field: SchemaFormField
  index: number
  onUpdate: (index: number, field: SchemaFormField) => void
  onRemove: (index: number) => void
}) {
  return (
    <div className="flex items-start gap-3 rounded-lg border border-border/50 bg-muted/30 p-3">
      <div className="flex-1 space-y-3">
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label className="text-xs text-muted-foreground">Field name</Label>
            <Input
              placeholder="field_name"
              value={field.name}
              onChange={(e) =>
                onUpdate(index, { ...field, name: e.target.value })
              }
              className="h-8"
            />
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs text-muted-foreground">Type</Label>
            <Select
              value={field.type}
              onValueChange={(value: FieldType) =>
                onUpdate(index, { ...field, type: value })
              }
            >
              <SelectTrigger className="h-8">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {FIELD_TYPES.map((type) => (
                  <SelectItem key={type} value={type}>
                    {type}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Checkbox
            id={`nullable-${index}`}
            checked={!field.required}
            onCheckedChange={(checked) =>
              onUpdate(index, { ...field, required: !checked })
            }
          />
          <Label
            htmlFor={`nullable-${index}`}
            className="text-xs text-muted-foreground"
          >
            Nullable
          </Label>
        </div>
      </div>
      <Button
        variant="ghost"
        size="icon"
        className="size-8 shrink-0 text-muted-foreground hover:text-destructive"
        onClick={() => onRemove(index)}
      >
        <X className="size-4" />
      </Button>
    </div>
  )
}

function SchemaDialog({
  open,
  onOpenChange,
  schema,
  onSave,
  isPending,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  schema?: BaseCampSchema
  onSave: (data: SchemaFormData) => void
  isPending: boolean
}) {
  const [formData, setFormData] = useState<SchemaFormData>(initialFormData)

  // Reset form data when dialog opens or schema changes
  useEffect(() => {
    if (open) {
      if (schema) {
        setFormData({
          name: schema.name,
          description: schema.description || "",
          fields: schema.fields.map((f) => ({
            name: f.name,
            type: f.type as FieldType,
            required: f.required,
            description: f.description,
          })),
        })
      } else {
        setFormData(initialFormData)
      }
    }
  }, [open, schema])

  const handleAddField = () => {
    setFormData((prev) => ({
      ...prev,
      fields: [
        ...prev.fields,
        { name: "", type: "str" as FieldType, required: true },
      ],
    }))
  }

  const handleUpdateField = (index: number, field: SchemaFormField) => {
    setFormData((prev) => ({
      ...prev,
      fields: prev.fields.map((f, i) => (i === index ? field : f)),
    }))
  }

  const handleRemoveField = (index: number) => {
    setFormData((prev) => ({
      ...prev,
      fields: prev.fields.filter((_, i) => i !== index),
    }))
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    onSave(formData)
  }

  const isEditing = !!schema

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-xl">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>
              {isEditing ? "Edit schema" : "Create schema"}
            </DialogTitle>
            <DialogDescription>
              {isEditing
                ? "Update the schema definition and fields"
                : "Define a new data schema for your ingested files"}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-6 py-6">
            <div className="space-y-2">
              <Label htmlFor="name">Name</Label>
              <Input
                id="name"
                placeholder="my_schema"
                value={formData.name}
                onChange={(e) =>
                  setFormData((prev) => ({ ...prev, name: e.target.value }))
                }
                required
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="description">Description</Label>
              <Textarea
                id="description"
                placeholder="Describe the purpose of this schema..."
                value={formData.description}
                onChange={(e) =>
                  setFormData((prev) => ({
                    ...prev,
                    description: e.target.value,
                  }))
                }
                rows={3}
              />
            </div>

            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <Label>Fields</Label>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={handleAddField}
                  className="gap-1.5"
                >
                  <Plus className="size-3.5" />
                  Add field
                </Button>
              </div>

              {formData.fields.length === 0 ? (
                <div className="flex h-24 items-center justify-center rounded-lg border-2 border-dashed border-border/50 bg-muted/30">
                  <p className="text-sm text-muted-foreground">
                    No fields defined yet
                  </p>
                </div>
              ) : (
                <div className="space-y-2">
                  {formData.fields.map((field, index) => (
                    <FieldEditor
                      key={index}
                      field={field}
                      index={index}
                      onUpdate={handleUpdateField}
                      onRemove={handleRemoveField}
                    />
                  ))}
                </div>
              )}
            </div>
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={isPending || !formData.name}>
              {isPending ? "Saving..." : isEditing ? "Update" : "Create"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function SchemaCard({
  schema,
  onEdit,
  onDelete,
}: {
  schema: BaseCampSchema
  onEdit: (schema: BaseCampSchema) => void
  onDelete: (schema: BaseCampSchema) => void
}) {
  const [isExpanded, setIsExpanded] = useState(false)
  const status = getSchemaStatus(schema)

  return (
    <Card className="border-border/50 bg-card transition-colors hover:bg-muted/30">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <Button
              variant="ghost"
              size="icon"
              className="size-6 shrink-0"
              onClick={() => setIsExpanded(!isExpanded)}
            >
              {isExpanded ? (
                <ChevronDown className="size-4" />
              ) : (
                <ChevronRight className="size-4" />
              )}
            </Button>
            <div>
              <div className="flex items-center gap-2">
                <CardTitle className="text-base">{schema.name}</CardTitle>
                <StatusBadge status={status} />
              </div>
              {schema.description && (
                <CardDescription className="mt-1">
                  {schema.description}
                </CardDescription>
              )}
            </div>
          </div>

          <div className="flex items-center gap-2">
            <div className="flex flex-col items-end gap-1 text-xs text-muted-foreground">
              <span>{schema.fields.length} fields</span>
              <span>{formatDate(schema.created_at)}</span>
            </div>

            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="icon" className="size-8">
                  <MoreHorizontal className="size-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onClick={() => onEdit(schema)}>
                  <Pencil className="mr-2 size-4" />
                  Edit
                </DropdownMenuItem>
                <DropdownMenuItem
                  className="text-destructive focus:text-destructive"
                  onClick={() => onDelete(schema)}
                >
                  <Trash2 className="mr-2 size-4" />
                  Delete
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      </CardHeader>

      {isExpanded && schema.fields.length > 0 && (
        <CardContent className="pt-0">
          <div className="rounded-lg border border-border/50 bg-muted/20">
            <div className="grid grid-cols-3 gap-4 border-b border-border/50 px-4 py-2 text-xs font-medium text-muted-foreground">
              <span>Name</span>
              <span>Type</span>
              <span>Required</span>
            </div>
            <div className="divide-y divide-border/50">
              {schema.fields.map((field, index) => (
                <div
                  key={index}
                  className="grid grid-cols-3 gap-4 px-4 py-2 text-sm"
                >
                  <span className="font-mono text-xs">{field.name}</span>
                  <Badge variant="secondary" className="w-fit text-xs">
                    {field.type}
                  </Badge>
                  <span className="text-muted-foreground">
                    {field.required ? "Yes" : "No"}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </CardContent>
      )}
    </Card>
  )
}

function EmptyState({ onCreateClick }: { onCreateClick: () => void }) {
  return (
    <Card className="border-border/50 bg-card">
      <CardContent className="flex flex-col items-center justify-center py-16">
        <div className="mb-4 rounded-full bg-muted/50 p-4">
          <Layers className="size-8 text-muted-foreground" />
        </div>
        <h3 className="mb-2 text-lg font-semibold">No schemas yet</h3>
        <p className="mb-6 max-w-sm text-center text-sm text-muted-foreground">
          Create your first schema to define the structure for your ingested
          data files.
        </p>
        <Button onClick={onCreateClick} className="gap-2">
          <Plus className="size-4" />
          Create your first schema
        </Button>
      </CardContent>
    </Card>
  )
}

export default function BaseCampSchemasPage() {
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingSchema, setEditingSchema] = useState<BaseCampSchema | undefined>()

  const {
    schemas,
    schemasLoading,
    createSchema,
    createSchemaPending,
    updateSchema,
    updateSchemaPending,
    deleteSchema,
    deleteSchemaPending,
  } = useBaseCampSchemas()

  const handleOpenCreateDialog = () => {
    setEditingSchema(undefined)
    setDialogOpen(true)
  }

  const handleOpenEditDialog = (schema: BaseCampSchema) => {
    setEditingSchema(schema)
    setDialogOpen(true)
  }

  const handleDelete = async (schema: BaseCampSchema) => {
    if (window.confirm(`Are you sure you want to delete "${schema.name}"?`)) {
      await deleteSchema(schema.id)
    }
  }

  const handleSave = async (data: SchemaFormData) => {
    const schemaData = {
      name: data.name,
      description: data.description || undefined,
      fields: data.fields.map((f) => ({
        name: f.name,
        type: f.type,
        required: f.required,
        description: f.description,
      })),
    }

    if (editingSchema) {
      await updateSchema({ id: editingSchema.id, data: schemaData })
    } else {
      await createSchema(schemaData)
    }
    setDialogOpen(false)
    setEditingSchema(undefined)
  }

  if (schemasLoading) {
    return <CenteredSpinner />
  }

  const isPending = createSchemaPending || updateSchemaPending

  return (
    <div className="size-full overflow-auto">
      <div className="container flex h-full flex-col space-y-8 py-8">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Schemas</h1>
            <p className="text-muted-foreground">
              Manage data schemas for your ingested files
            </p>
          </div>
          <Button onClick={handleOpenCreateDialog} className="gap-2">
            <Plus className="size-4" />
            Create schema
          </Button>
        </div>

        {/* Schema List */}
        {!schemas || schemas.length === 0 ? (
          <EmptyState onCreateClick={handleOpenCreateDialog} />
        ) : (
          <div className="space-y-4">
            {schemas.map((schema) => (
              <SchemaCard
                key={schema.id}
                schema={schema}
                onEdit={handleOpenEditDialog}
                onDelete={handleDelete}
              />
            ))}
          </div>
        )}

        {/* Create/Edit Dialog */}
        <SchemaDialog
          open={dialogOpen}
          onOpenChange={(open) => {
            setDialogOpen(open)
            if (!open) {
              setEditingSchema(undefined)
            }
          }}
          schema={editingSchema}
          onSave={handleSave}
          isPending={isPending}
        />
      </div>
    </div>
  )
}
