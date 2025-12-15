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

export interface FilePathItem {
  path: string
  description: string
}

export interface CreateDatasetRequest {
  dtype: string
  name: string
  summary: string
  tags: string
  configuration: {
    collectionName: string
    filePaths: FilePathItem[]
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

export interface EndpointListItem {
  id: string
  name: string
  slug: string
}

export interface ProvisionerStatusResponse {
  status: string
  error?: string
}

export interface DatasetListItem {
  id: string
  name: string
  dtype: string
  summary: string
  tags: string
  created_at: string
  configuration: Record<string, unknown>
  connected_endpoints: EndpointListItem[]
  provisioner_status?: ProvisionerStatusResponse
}

export interface UpdateDatasetRequest {
  name?: string
  summary?: string
  tags?: string
}
