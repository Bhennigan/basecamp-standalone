"use client"

import {
  Activity,
  Database,
  FileUp,
  GitBranch,
  Layers,
  Plug,
  RefreshCw,
  Upload,
} from "lucide-react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { CenteredSpinner } from "@/components/loading/spinner"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  useBaseCampJobs,
  useBaseCampRecords,
  useBaseCampSchemas,
  useBaseCampSources,
  useBaseCampMappings,
  useBaseCampConsumers,
} from "@/hooks/use-basecamp"
import { useWorkspaceId } from "@/providers/workspace-id"

function MetricCard({
  title,
  value,
  icon: Icon,
  description,
}: {
  title: string
  value: number | string
  icon: React.ComponentType<{ className?: string }>
  description?: string
}) {
  return (
    <Card className="border-border/50 bg-card">
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">
          {title}
        </CardTitle>
        <Icon className="size-4 text-muted-foreground" />
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">{value}</div>
        {description && (
          <p className="text-xs text-muted-foreground">{description}</p>
        )}
      </CardContent>
    </Card>
  )
}

function JobStatusBadge({ status }: { status: string }) {
  const variants: Record<
    string,
    { variant: "default" | "secondary" | "destructive" | "outline"; label: string }
  > = {
    pending: { variant: "outline", label: "Pending" },
    received: { variant: "outline", label: "Received" },
    running: { variant: "secondary", label: "Running" },
    analyzing: { variant: "secondary", label: "Analyzing" },
    validating: { variant: "secondary", label: "Validating" },
    transforming: { variant: "secondary", label: "Transforming" },
    loading: { variant: "secondary", label: "Loading" },
    complete: { variant: "default", label: "Completed" },
    completed: { variant: "default", label: "Completed" },
    failed: { variant: "destructive", label: "Failed" },
  }

  const { variant, label } = variants[status?.toLowerCase()] || {
    variant: "outline" as const,
    label: status || "Unknown",
  }

  return <Badge variant={variant}>{label}</Badge>
}

function formatTimeAgo(dateString: string): string {
  const date = new Date(dateString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMins / 60)
  const diffDays = Math.floor(diffHours / 24)

  if (diffMins < 1) return "Just now"
  if (diffMins < 60) return `${diffMins}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  return `${diffDays}d ago`
}

export default function BaseCampPage() {
  const workspaceId = useWorkspaceId()
  const router = useRouter()

  const { sources, sourcesLoading } = useBaseCampSources()
  const { schemas, schemasLoading } = useBaseCampSchemas()
  const { records, recordsLoading } = useBaseCampRecords()
  const { jobs, jobsLoading, refetchJobs } = useBaseCampJobs()
  const { mappings, mappingsLoading } = useBaseCampMappings()
  const { consumers, consumersLoading } = useBaseCampConsumers()

  const isLoading =
    sourcesLoading || schemasLoading || recordsLoading || jobsLoading

  if (isLoading) {
    return <CenteredSpinner />
  }

  const activeJobs = jobs?.filter(
    (job: any) => {
      const s = (job.state || job.status || "").toLowerCase()
      return s !== "complete" && s !== "completed" && s !== "failed"
    }
  ).length || 0

  const recentJobs = jobs?.slice(0, 5) || []

  const basePath = `/basecamp`

  return (
    <div className="size-full overflow-auto">
      <div className="container flex h-full flex-col space-y-8 py-8">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Base Camp</h1>
            <p className="text-muted-foreground">Data Fusion Platform</p>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => refetchJobs()}
              className="gap-2"
            >
              <RefreshCw className="size-4" />
              Refresh
            </Button>
          </div>
        </div>

        {/* Metrics Grid */}
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
          <MetricCard
            title="Total Sources"
            value={sources?.length || 0}
            icon={Database}
            description="Connected data sources"
          />
          <MetricCard
            title="Total Schemas"
            value={schemas?.length || 0}
            icon={Layers}
            description="Defined data schemas"
          />
          <MetricCard
            title="Total Records"
            value={records?.length || 0}
            icon={FileUp}
            description="Ingested records"
          />
          <MetricCard
            title="Active Jobs"
            value={activeJobs}
            icon={Activity}
            description="Running ingestion jobs"
          />
          <MetricCard
            title="Mappings"
            value={mappings?.length || 0}
            icon={GitBranch}
            description="Transform profiles"
          />
          <MetricCard
            title="Consumers"
            value={consumers?.length || 0}
            icon={Plug}
            description="Registered consumers"
          />
        </div>

        {/* Main Content Grid */}
        <div className="grid gap-6 lg:grid-cols-2">
          {/* Recent Activity */}
          <Card className="border-border/50 bg-card">
            <CardHeader>
              <CardTitle>Recent activity</CardTitle>
              <CardDescription>
                Latest ingestion jobs and operations
              </CardDescription>
            </CardHeader>
            <CardContent>
              {recentJobs.length === 0 ? (
                <div className="flex h-32 items-center justify-center text-muted-foreground">
                  No recent activity
                </div>
              ) : (
                <div className="space-y-4">
                  {recentJobs.map((job) => (
                    <div
                      key={job.id}
                      className="flex items-center justify-between rounded-lg border border-border/50 bg-muted/30 p-3"
                    >
                      <div className="flex flex-col gap-1">
                        <span className="text-sm font-medium">
                          Job {job.id.slice(0, 8)}...
                        </span>
                        <span className="text-xs text-muted-foreground">
                          {(job as any).processed_records ?? job.records_processed ?? 0} records processed
                        </span>
                      </div>
                      <div className="flex items-center gap-3">
                        <span className="text-xs text-muted-foreground">
                          {formatTimeAgo(job.created_at)}
                        </span>
                        <JobStatusBadge status={(job as any).state || job.status} />
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Quick Actions */}
          <Card className="border-border/50 bg-card">
            <CardHeader>
              <CardTitle>Quick actions</CardTitle>
              <CardDescription>
                Common operations and shortcuts
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid gap-3">
                <Button
                  variant="outline"
                  className="h-auto justify-start gap-3 p-4"
                  onClick={() => router.push(`${basePath}/upload`)}
                >
                  <Upload className="size-5" />
                  <div className="flex flex-col items-start">
                    <span className="font-medium">Upload file</span>
                    <span className="text-xs text-muted-foreground">
                      Import CSV, JSON, or Parquet files
                    </span>
                  </div>
                </Button>
                <Button
                  variant="outline"
                  className="h-auto justify-start gap-3 p-4"
                  onClick={() => router.push(`${basePath}/schemas`)}
                >
                  <Layers className="size-5" />
                  <div className="flex flex-col items-start">
                    <span className="font-medium">Create schema</span>
                    <span className="text-xs text-muted-foreground">
                      Define a new data schema
                    </span>
                  </div>
                </Button>
                <Button
                  variant="outline"
                  className="h-auto justify-start gap-3 p-4"
                  onClick={() => router.push(`${basePath}/sources`)}
                >
                  <Database className="size-5" />
                  <div className="flex flex-col items-start">
                    <span className="font-medium">Add data source</span>
                    <span className="text-xs text-muted-foreground">
                      Connect a new data source
                    </span>
                  </div>
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Navigation Links */}
        <div className="grid gap-4 md:grid-cols-3 lg:grid-cols-6">
          <Link href={`${basePath}/upload`}>
            <Card className="cursor-pointer border-border/50 bg-card transition-colors hover:bg-muted/50">
              <CardContent className="flex items-center gap-3 p-4">
                <Upload className="size-5 text-muted-foreground" />
                <span className="font-medium">Upload</span>
              </CardContent>
            </Card>
          </Link>
          <Link href={`${basePath}/schemas`}>
            <Card className="cursor-pointer border-border/50 bg-card transition-colors hover:bg-muted/50">
              <CardContent className="flex items-center gap-3 p-4">
                <Layers className="size-5 text-muted-foreground" />
                <span className="font-medium">Schemas</span>
              </CardContent>
            </Card>
          </Link>
          <Link href={`${basePath}/data`}>
            <Card className="cursor-pointer border-border/50 bg-card transition-colors hover:bg-muted/50">
              <CardContent className="flex items-center gap-3 p-4">
                <FileUp className="size-5 text-muted-foreground" />
                <span className="font-medium">Data</span>
              </CardContent>
            </Card>
          </Link>
          <Link href={`${basePath}/sources`}>
            <Card className="cursor-pointer border-border/50 bg-card transition-colors hover:bg-muted/50">
              <CardContent className="flex items-center gap-3 p-4">
                <Database className="size-5 text-muted-foreground" />
                <span className="font-medium">Sources</span>
              </CardContent>
            </Card>
          </Link>
          <Link href={`${basePath}/mappings`}>
            <Card className="cursor-pointer border-border/50 bg-card transition-colors hover:bg-muted/50">
              <CardContent className="flex items-center gap-3 p-4">
                <GitBranch className="size-5 text-muted-foreground" />
                <span className="font-medium">Mappings</span>
              </CardContent>
            </Card>
          </Link>
          <Link href={`${basePath}/consumers`}>
            <Card className="cursor-pointer border-border/50 bg-card transition-colors hover:bg-muted/50">
              <CardContent className="flex items-center gap-3 p-4">
                <Plug className="size-5 text-muted-foreground" />
                <span className="font-medium">Consumers</span>
              </CardContent>
            </Card>
          </Link>
        </div>
      </div>
    </div>
  )
}
