"use client"

import { useState } from "react"
import {
  Plus,
  MoreHorizontal,
  Pencil,
  Trash2,
  Upload,
  Globe,
  Workflow,
  Clock,
  Power,
  PowerOff,
  Database,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import {
  useBaseCampSources,
  useBaseCampSchemas,
  type BaseCampDataSource,
  type BaseCampDataSourceCreate,
  type BaseCampDataSourceUpdate,
} from "@/hooks/use-basecamp"
import { CenteredSpinner } from "@/components/loading/spinner"
import { toast } from "@/components/ui/use-toast"

const SOURCE_TYPES = [
  { value: "FILE_UPLOAD", label: "File upload", icon: Upload },
  { value: "API_ENDPOINT", label: "API endpoint", icon: Globe },
  { value: "TRACECAT_TRIGGER", label: "Tracecat trigger", icon: Workflow },
  { value: "SCHEDULED", label: "Scheduled", icon: Clock },
] as const

type SourceType = (typeof SOURCE_TYPES)[number]["value"]

function getSourceTypeIcon(type: string) {
  const sourceType = SOURCE_TYPES.find((t) => t.value === type)
  return sourceType?.icon || Database
}

function getSourceTypeLabel(type: string) {
  const sourceType = SOURCE_TYPES.find((t) => t.value === type)
  return sourceType?.label || type
}

interface SourceFormData {
  name: string
  type: SourceType
  description: string
  schemaId: string
  config: string
  isActive: boolean
}

const defaultFormData: SourceFormData = {
  name: "",
  type: "FILE_UPLOAD",
  description: "",
  schemaId: "",
  config: "{}",
  isActive: true,
}

function SourceCard({
  source,
  onEdit,
  onDelete,
  onToggleStatus,
}: {
  source: BaseCampDataSource
  onEdit: (source: BaseCampDataSource) => void
  onDelete: (source: BaseCampDataSource) => void
  onToggleStatus: (source: BaseCampDataSource) => void
}) {
  const Icon = getSourceTypeIcon(source.type)
  const isActive = source.status === "active"
  const isError = source.status === "error"

  return (
    <Card className="rounded-xl border-border/50 bg-card transition-colors hover:border-border">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className="flex size-10 items-center justify-center rounded-lg bg-muted/50">
              <Icon className="size-5 text-muted-foreground" />
            </div>
            <div className="flex flex-col gap-1">
              <CardTitle className="text-base">{source.name}</CardTitle>
              <div className="flex items-center gap-2">
                <Badge variant="secondary" className="text-xs">
                  {getSourceTypeLabel(source.type)}
                </Badge>
                <Badge
                  variant={isError ? "destructive" : isActive ? "default" : "outline"}
                  className="text-xs"
                >
                  {isError ? "Error" : isActive ? "Active" : "Inactive"}
                </Badge>
              </div>
            </div>
          </div>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" className="size-8">
                <MoreHorizontal className="size-4" />
                <span className="sr-only">Open menu</span>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={() => onEdit(source)}>
                <Pencil className="mr-2 size-4" />
                Edit
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => onToggleStatus(source)}>
                {isActive ? (
                  <>
                    <PowerOff className="mr-2 size-4" />
                    Deactivate
                  </>
                ) : (
                  <>
                    <Power className="mr-2 size-4" />
                    Activate
                  </>
                )}
              </DropdownMenuItem>
              <DropdownMenuItem
                onClick={() => onDelete(source)}
                className="text-destructive focus:text-destructive"
              >
                <Trash2 className="mr-2 size-4" />
                Delete
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </CardHeader>
      <CardContent>
        <CardDescription className="line-clamp-2 text-sm">
          {source.config?.description ||
            `${getSourceTypeLabel(source.type)} data source`}
        </CardDescription>
        <div className="mt-3 flex items-center justify-between text-xs text-muted-foreground">
          <span>
            Created {new Date(source.created_at).toLocaleDateString()}
          </span>
          <span>
            Updated {new Date(source.updated_at).toLocaleDateString()}
          </span>
        </div>
      </CardContent>
    </Card>
  )
}

function EmptyState({ onCreateClick }: { onCreateClick: () => void }) {
  return (
    <Card className="rounded-xl border-2 border-dashed border-border/50 bg-card">
      <CardContent className="flex flex-col items-center justify-center py-16">
        <div className="flex size-16 items-center justify-center rounded-full bg-muted/50">
          <Database className="size-8 text-muted-foreground" />
        </div>
        <h3 className="mt-4 text-lg font-semibold">No data sources</h3>
        <p className="mt-1 text-center text-sm text-muted-foreground">
          Get started by creating your first data source to ingest data into
          Base Camp.
        </p>
        <Button onClick={onCreateClick} className="mt-6 gap-2">
          <Plus className="size-4" />
          Add source
        </Button>
      </CardContent>
    </Card>
  )
}

function SourceDialog({
  open,
  onOpenChange,
  source,
  onSubmit,
  isSubmitting,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  source: BaseCampDataSource | null
  onSubmit: (data: SourceFormData) => Promise<void>
  isSubmitting: boolean
}) {
  const { schemas } = useBaseCampSchemas()
  const [formData, setFormData] = useState<SourceFormData>(defaultFormData)
  const [configError, setConfigError] = useState<string | null>(null)

  const isEditing = !!source

  // Reset form when dialog opens/closes or source changes
  const handleOpenChange = (newOpen: boolean) => {
    if (newOpen && source) {
      setFormData({
        name: source.name,
        type: source.type as SourceType,
        description: (source.config?.description as string) || "",
        schemaId: (source.config?.schema_id as string) || "",
        config: JSON.stringify(source.config || {}, null, 2),
        isActive: source.status === "active",
      })
    } else if (newOpen) {
      setFormData(defaultFormData)
    }
    setConfigError(null)
    onOpenChange(newOpen)
  }

  const validateConfig = (configString: string): boolean => {
    try {
      JSON.parse(configString)
      setConfigError(null)
      return true
    } catch {
      setConfigError("Invalid JSON configuration")
      return false
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    if (!formData.name.trim()) {
      toast({
        title: "Validation error",
        description: "Source name is required",
        variant: "destructive",
      })
      return
    }

    if (!validateConfig(formData.config)) {
      return
    }

    await onSubmit(formData)
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>
            {isEditing ? "Edit source" : "Create new source"}
          </DialogTitle>
          <DialogDescription>
            {isEditing
              ? "Update the configuration for this data source."
              : "Configure a new data source to ingest data into Base Camp."}
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="name">Name *</Label>
            <Input
              id="name"
              placeholder="My data source"
              value={formData.name}
              onChange={(e) =>
                setFormData({ ...formData, name: e.target.value })
              }
              required
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="type">Source type</Label>
            <Select
              value={formData.type}
              onValueChange={(value: SourceType) =>
                setFormData({ ...formData, type: value })
              }
            >
              <SelectTrigger id="type">
                <SelectValue placeholder="Select source type" />
              </SelectTrigger>
              <SelectContent>
                {SOURCE_TYPES.map((type) => {
                  const TypeIcon = type.icon
                  return (
                    <SelectItem key={type.value} value={type.value}>
                      <div className="flex items-center gap-2">
                        <TypeIcon className="size-4" />
                        {type.label}
                      </div>
                    </SelectItem>
                  )
                })}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="description">Description</Label>
            <Textarea
              id="description"
              placeholder="Describe this data source..."
              value={formData.description}
              onChange={(e) =>
                setFormData({ ...formData, description: e.target.value })
              }
              rows={2}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="schema">Schema (optional)</Label>
            <Select
              value={formData.schemaId || "__none__"}
              onValueChange={(value) =>
                setFormData({ ...formData, schemaId: value === "__none__" ? "" : value })
              }
            >
              <SelectTrigger id="schema">
                <SelectValue placeholder="Select a schema" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__none__">None</SelectItem>
                {schemas?.map((schema) => (
                  <SelectItem key={schema.id} value={schema.id}>
                    {schema.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="config">Configuration (JSON)</Label>
            <Textarea
              id="config"
              placeholder="{}"
              value={formData.config}
              onChange={(e) => {
                setFormData({ ...formData, config: e.target.value })
                if (configError) validateConfig(e.target.value)
              }}
              rows={4}
              className="font-mono text-sm"
            />
            {configError && (
              <p className="text-sm text-destructive">{configError}</p>
            )}
          </div>

          <div className="flex items-center justify-between rounded-lg border border-border/50 p-3">
            <div className="space-y-0.5">
              <Label htmlFor="active">Active</Label>
              <p className="text-xs text-muted-foreground">
                Enable this source to start receiving data
              </p>
            </div>
            <Switch
              id="active"
              checked={formData.isActive}
              onCheckedChange={(checked) =>
                setFormData({ ...formData, isActive: checked })
              }
            />
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting
                ? isEditing
                  ? "Saving..."
                  : "Creating..."
                : isEditing
                  ? "Save changes"
                  : "Create source"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function DeleteConfirmDialog({
  open,
  onOpenChange,
  source,
  onConfirm,
  isDeleting,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  source: BaseCampDataSource | null
  onConfirm: () => Promise<void>
  isDeleting: boolean
}) {
  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Delete source</AlertDialogTitle>
          <AlertDialogDescription>
            Are you sure you want to delete &ldquo;{source?.name}&rdquo;? This
            action cannot be undone and will remove all associated
            configurations.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction
            onClick={onConfirm}
            disabled={isDeleting}
            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
          >
            {isDeleting ? "Deleting..." : "Delete"}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}

export default function BaseCampSourcesPage() {
  const {
    sources,
    sourcesLoading,
    createSource,
    createSourcePending,
    updateSource,
    updateSourcePending,
    deleteSource,
    deleteSourcePending,
  } = useBaseCampSources()

  const [dialogOpen, setDialogOpen] = useState(false)
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [selectedSource, setSelectedSource] =
    useState<BaseCampDataSource | null>(null)

  if (sourcesLoading) {
    return <CenteredSpinner />
  }

  const handleCreateClick = () => {
    setSelectedSource(null)
    setDialogOpen(true)
  }

  const handleEditClick = (source: BaseCampDataSource) => {
    setSelectedSource(source)
    setDialogOpen(true)
  }

  const handleDeleteClick = (source: BaseCampDataSource) => {
    setSelectedSource(source)
    setDeleteDialogOpen(true)
  }

  const handleToggleStatus = async (source: BaseCampDataSource) => {
    try {
      const newStatus = source.status === "active" ? "inactive" : "active"
      await updateSource({
        id: source.id,
        data: { status: newStatus },
      })
      toast({
        title: "Source updated",
        description: `Source "${source.name}" has been ${newStatus === "active" ? "activated" : "deactivated"}.`,
      })
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to update source status.",
        variant: "destructive",
      })
    }
  }

  const handleSubmit = async (formData: SourceFormData) => {
    try {
      const config: Record<string, unknown> = JSON.parse(formData.config)
      if (formData.description) {
        config.description = formData.description
      }
      if (formData.schemaId) {
        config.schema_id = formData.schemaId
      }

      if (selectedSource) {
        // Update existing source
        const updateData: BaseCampDataSourceUpdate = {
          name: formData.name,
          config,
          status: formData.isActive ? "active" : "inactive",
        }
        await updateSource({ id: selectedSource.id, data: updateData })
        toast({
          title: "Source updated",
          description: `Source "${formData.name}" has been updated.`,
        })
      } else {
        // Create new source
        const createData: BaseCampDataSourceCreate = {
          name: formData.name,
          type: formData.type,
          config,
        }
        await createSource(createData)
        toast({
          title: "Source created",
          description: `Source "${formData.name}" has been created.`,
        })
      }
      setDialogOpen(false)
    } catch (error) {
      toast({
        title: "Error",
        description: selectedSource
          ? "Failed to update source."
          : "Failed to create source.",
        variant: "destructive",
      })
    }
  }

  const handleDelete = async () => {
    if (!selectedSource) return

    try {
      await deleteSource(selectedSource.id)
      toast({
        title: "Source deleted",
        description: `Source "${selectedSource.name}" has been deleted.`,
      })
      setDeleteDialogOpen(false)
      setSelectedSource(null)
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to delete source.",
        variant: "destructive",
      })
    }
  }

  const hasSources = sources && sources.length > 0

  return (
    <div className="size-full overflow-auto">
      <div className="container flex h-full flex-col space-y-8 py-8">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Data Sources</h1>
            <p className="text-muted-foreground">
              Configure and manage your data sources
            </p>
          </div>
          <Button onClick={handleCreateClick} className="gap-2">
            <Plus className="size-4" />
            Add source
          </Button>
        </div>

        {/* Content */}
        {hasSources ? (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {sources.map((source) => (
              <SourceCard
                key={source.id}
                source={source}
                onEdit={handleEditClick}
                onDelete={handleDeleteClick}
                onToggleStatus={handleToggleStatus}
              />
            ))}
          </div>
        ) : (
          <EmptyState onCreateClick={handleCreateClick} />
        )}

        {/* Dialogs */}
        <SourceDialog
          open={dialogOpen}
          onOpenChange={setDialogOpen}
          source={selectedSource}
          onSubmit={handleSubmit}
          isSubmitting={createSourcePending || updateSourcePending}
        />

        <DeleteConfirmDialog
          open={deleteDialogOpen}
          onOpenChange={setDeleteDialogOpen}
          source={selectedSource}
          onConfirm={handleDelete}
          isDeleting={deleteSourcePending}
        />
      </div>
    </div>
  )
}
