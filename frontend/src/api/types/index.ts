export interface FileItem {
  name: string
  path: string
  is_dir: boolean
  size?: number
  modified: string
  extension?: string
}

export interface BrowseResponse {
  path: string
  parent?: string
  items: FileItem[]
}

export interface CreateDatasetRequest {
  dtype: string
  name: string
  summary: string
  tags: string
  configuration: {
    collectionName: string
    filePaths: string[]
  }
}

export interface DatasetResponse {
  id: string
  name: string
  dtype: string
  configuration: Record<string, unknown>
  summary: string
  tags: string
  created_at: string
  updated_at: string
}