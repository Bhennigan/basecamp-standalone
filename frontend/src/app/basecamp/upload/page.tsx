"use client"

import Link from "next/link"
import { useCallback, useState } from "react"
import {
  Upload,
  FileSpreadsheet,
  FileJson,
  FileText,
  CheckCircle,
  XCircle,
  Clock,
  Loader2,
  File,
  RefreshCw,
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
import { Progress } from "@/components/ui/progress"
import { toast } from "@/components/ui/use-toast"
import { cn } from "@/lib/utils"
import { useWorkspaceId } from "@/providers/workspace-id"
import {
  useBaseCampUpload,
  useBaseCampJobs,
  type BaseCampIngestionJob,
} from "@/hooks/use-basecamp"

const FILE_EXTENSIONS = [".csv", ".json", ".jsonl", ".xlsx", ".xls"]

type UploadState = "idle" | "selected" | "uploading" | "complete" | "error"

interface UploadedFile {
  file: File
  jobId?: string
  error?: string
}

function getFileIcon(filename: string) {
  const ext = filename.toLowerCase().split(".").pop()
  switch (ext) {
    case "csv":
      return <FileSpreadsheet className="size-5 text-green-500" />
    case "json":
    case "jsonl":
      return <FileJson className="size-5 text-yellow-500" />
    case "xlsx":
    case "xls":
      return <FileSpreadsheet className="size-5 text-blue-500" />
    default:
      return <FileText className="size-5 text-muted-foreground" />
  }
}

function formatFileSize(bytes: number): string {
  if (bytes === 0) return "0 Bytes"
  const k = 1024
  const sizes = ["Bytes", "KB", "MB", "GB"]
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${Number.parseFloat((bytes / k ** i).toFixed(2))} ${sizes[i]}`
}

function getStatusBadge(status: BaseCampIngestionJob["status"]) {
  switch (status) {
    case "pending":
      return (
        <Badge className="bg-yellow-500/10 text-yellow-500 hover:bg-yellow-500/20 border-yellow-500/20">
          <Clock className="mr-1 size-3" />
          Received
        </Badge>
      )
    case "running":
      return (
        <Badge className="bg-blue-500/10 text-blue-500 hover:bg-blue-500/20 border-blue-500/20">
          <Loader2 className="mr-1 size-3 animate-spin" />
          Analyzing
        </Badge>
      )
    case "completed":
      return (
        <Badge className="bg-green-500/10 text-green-500 hover:bg-green-500/20 border-green-500/20">
          <CheckCircle className="mr-1 size-3" />
          Complete
        </Badge>
      )
    case "failed":
      return (
        <Badge className="bg-red-500/10 text-red-500 hover:bg-red-500/20 border-red-500/20">
          <XCircle className="mr-1 size-3" />
          Failed
        </Badge>
      )
    default:
      return null
  }
}

function FileTypeIndicators() {
  return (
    <div className="flex items-center justify-center gap-4 mt-4">
      <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <FileSpreadsheet className="size-4 text-green-500" />
        <span>CSV</span>
      </div>
      <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <FileJson className="size-4 text-yellow-500" />
        <span>JSON/JSONL</span>
      </div>
      <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <FileSpreadsheet className="size-4 text-blue-500" />
        <span>Excel</span>
      </div>
    </div>
  )
}

export default function BaseCampUploadPage() {
  const workspaceId = useWorkspaceId()
  const { uploadFile } = useBaseCampUpload()
  const { jobs, jobsLoading, refetchJobs } = useBaseCampJobs()

  const [uploadState, setUploadState] = useState<UploadState>("idle")
  const [selectedFile, setSelectedFile] = useState<UploadedFile | null>(null)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [isDragOver, setIsDragOver] = useState(false)

  const isValidFileType = useCallback((file: File) => {
    const ext = `.${file.name.toLowerCase().split(".").pop()}`
    return FILE_EXTENSIONS.includes(ext)
  }, [])

  const handleFileSelect = useCallback(
    (file: File) => {
      if (!isValidFileType(file)) {
        toast({
          title: "Invalid file type",
          description: "Please upload a CSV, JSON, JSONL, or Excel file.",
          variant: "destructive",
        })
        return
      }
      setSelectedFile({ file })
      setUploadState("selected")
      setUploadProgress(0)
    },
    [isValidFileType]
  )

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragOver(true)
  }, [])

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragOver(false)
  }, [])

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      e.stopPropagation()
      setIsDragOver(false)

      const files = e.dataTransfer.files
      if (files.length > 0) {
        handleFileSelect(files[0])
      }
    },
    [handleFileSelect]
  )

  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = e.target.files
      if (files && files.length > 0) {
        handleFileSelect(files[0])
      }
    },
    [handleFileSelect]
  )

  const handleUpload = useCallback(async () => {
    if (!selectedFile?.file) return

    setUploadState("uploading")
    setUploadProgress(0)

    try {
      const response = await uploadFile({
        file: selectedFile.file,
        options: {
          onProgress: (progress) => {
            setUploadProgress(progress)
          },
        },
      })

      setSelectedFile((prev) =>
        prev ? { ...prev, jobId: response.job_id } : null
      )
      setUploadState("complete")
      toast({
        title: "Upload successful",
        description: `File uploaded. Job ID: ${response.job_id}`,
      })
      refetchJobs()
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : "Upload failed"
      setSelectedFile((prev) =>
        prev ? { ...prev, error: errorMessage } : null
      )
      setUploadState("error")
      toast({
        title: "Upload failed",
        description: errorMessage,
        variant: "destructive",
      })
    }
  }, [selectedFile, uploadFile, refetchJobs])

  const handleReset = useCallback(() => {
    setUploadState("idle")
    setSelectedFile(null)
    setUploadProgress(0)
  }, [])

  // Sort jobs by created_at descending (most recent first)
  const recentJobs = jobs
    ?.slice()
    .sort(
      (a, b) =>
        new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    )
    .slice(0, 10)

  return (
    <div className="flex flex-col min-h-0 max-w-4xl mx-auto my-16 px-8 space-y-8">
      {/* Upload Section */}
      <Card className="rounded-xl">
        <CardHeader>
          <CardTitle>Upload data</CardTitle>
          <CardDescription>
            Import data files into Base Camp for analysis and querying
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Drag and Drop Zone */}
          {(uploadState === "idle" || uploadState === "selected") && (
            <>
              <div
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                className={cn(
                  "relative flex flex-col items-center justify-center rounded-xl border-2 border-dashed p-12 transition-all cursor-pointer",
                  "border-muted-foreground/25 hover:border-primary/50 hover:bg-muted/50",
                  isDragOver && "border-primary bg-primary/5",
                  uploadState === "selected" && "border-primary/50 bg-muted/30"
                )}
              >
                <input
                  type="file"
                  accept={FILE_EXTENSIONS.join(",")}
                  onChange={handleInputChange}
                  className="absolute inset-0 opacity-0 cursor-pointer"
                />
                <div className="flex flex-col items-center text-center">
                  <div
                    className={cn(
                      "rounded-full p-4 mb-4 transition-colors",
                      isDragOver ? "bg-primary/10" : "bg-muted"
                    )}
                  >
                    <Upload
                      className={cn(
                        "size-8",
                        isDragOver ? "text-primary" : "text-muted-foreground"
                      )}
                    />
                  </div>
                  <p className="text-lg font-medium">
                    Drop files here or click to browse
                  </p>
                  <p className="text-sm text-muted-foreground mt-1">
                    Supported formats: CSV, JSON, JSONL, Excel (.xlsx, .xls)
                  </p>
                  <FileTypeIndicators />
                </div>
              </div>

              {/* Selected File Info */}
              {selectedFile && uploadState === "selected" && (
                <div className="flex items-center justify-between p-4 rounded-lg bg-muted/50 border">
                  <div className="flex items-center gap-3">
                    {getFileIcon(selectedFile.file.name)}
                    <div>
                      <p className="font-medium">{selectedFile.file.name}</p>
                      <p className="text-sm text-muted-foreground">
                        {formatFileSize(selectedFile.file.size)}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button variant="outline" size="sm" onClick={handleReset}>
                      Cancel
                    </Button>
                    <Button size="sm" onClick={handleUpload}>
                      <Upload className="mr-2 size-4" />
                      Upload
                    </Button>
                  </div>
                </div>
              )}
            </>
          )}

          {/* Uploading State */}
          {uploadState === "uploading" && selectedFile && (
            <div className="space-y-4 p-6 rounded-xl bg-muted/30 border">
              <div className="flex items-center gap-3">
                {getFileIcon(selectedFile.file.name)}
                <div className="flex-1">
                  <p className="font-medium">{selectedFile.file.name}</p>
                  <p className="text-sm text-muted-foreground">
                    Uploading... {uploadProgress}%
                  </p>
                </div>
                <Loader2 className="size-5 animate-spin text-primary" />
              </div>
              <Progress value={uploadProgress} className="h-2" />
            </div>
          )}

          {/* Complete State */}
          {uploadState === "complete" && selectedFile && (
            <div className="space-y-4 p-6 rounded-xl bg-green-500/5 border border-green-500/20">
              <div className="flex items-center gap-3">
                <CheckCircle className="size-8 text-green-500" />
                <div className="flex-1">
                  <p className="font-medium text-green-500">
                    Upload successful
                  </p>
                  <p className="text-sm text-muted-foreground">
                    {selectedFile.file.name}
                  </p>
                </div>
              </div>
              {selectedFile.jobId && (
                <div className="flex items-center justify-between p-3 rounded-lg bg-muted/50">
                  <div>
                    <p className="text-sm text-muted-foreground">Job ID</p>
                    <p className="font-mono text-sm">{selectedFile.jobId}</p>
                  </div>
                  <Link
                    href={`/basecamp/jobs/${selectedFile.jobId}`}
                  >
                    <Button variant="outline" size="sm">
                      View job
                    </Button>
                  </Link>
                </div>
              )}
              <Button onClick={handleReset} className="w-full">
                <Upload className="mr-2 size-4" />
                Upload another file
              </Button>
            </div>
          )}

          {/* Error State */}
          {uploadState === "error" && selectedFile && (
            <div className="space-y-4 p-6 rounded-xl bg-red-500/5 border border-red-500/20">
              <div className="flex items-center gap-3">
                <XCircle className="size-8 text-red-500" />
                <div className="flex-1">
                  <p className="font-medium text-red-500">Upload failed</p>
                  <p className="text-sm text-muted-foreground">
                    {selectedFile.error || "An unknown error occurred"}
                  </p>
                </div>
              </div>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  onClick={handleReset}
                  className="flex-1"
                >
                  Try again
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Recent Uploads Section */}
      <Card className="rounded-xl">
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle>Recent uploads</CardTitle>
            <CardDescription>
              Recent ingestion jobs and their status
            </CardDescription>
          </div>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => refetchJobs()}
            disabled={jobsLoading}
          >
            <RefreshCw
              className={cn("size-4", jobsLoading && "animate-spin")}
            />
          </Button>
        </CardHeader>
        <CardContent>
          {jobsLoading && !recentJobs ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="size-6 animate-spin text-muted-foreground" />
            </div>
          ) : recentJobs && recentJobs.length > 0 ? (
            <div className="space-y-2">
              {recentJobs.map((job) => (
                <Link
                  key={job.id}
                  href={`/basecamp/jobs/${job.id}`}
                  className="block"
                >
                  <div className="flex items-center justify-between p-3 rounded-lg border bg-card hover:bg-muted/50 transition-colors">
                    <div className="flex items-center gap-3">
                      <File className="size-4 text-muted-foreground" />
                      <div>
                        <p className="font-mono text-sm">{job.id}</p>
                        <p className="text-xs text-muted-foreground">
                          {new Date(job.created_at).toLocaleString()}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-4">
                      {(job.status === "completed" ||
                        job.status === "failed") && (
                        <div className="text-right text-xs text-muted-foreground">
                          <p>
                            {job.records_processed.toLocaleString()} processed
                          </p>
                          {job.records_failed > 0 && (
                            <p className="text-red-500">
                              {job.records_failed.toLocaleString()} failed
                            </p>
                          )}
                        </div>
                      )}
                      {getStatusBadge(job.status)}
                    </div>
                  </div>
                </Link>
              ))}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-8 text-center">
              <File className="size-8 text-muted-foreground mb-2" />
              <p className="text-sm text-muted-foreground">
                No recent uploads found
              </p>
              <p className="text-xs text-muted-foreground">
                Upload a file to get started
              </p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
