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