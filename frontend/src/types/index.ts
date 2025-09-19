export interface Service {
  id: string
  name: string
  description: string
  status: 'active' | 'inactive'
  lastUpdated: string
}

export interface Message {
  id: string
  title: string
  content: string
  source: string
  type: 'info' | 'success' | 'alert'
  time: string
  read: boolean
  actionable: boolean
}

export interface Transaction {
  id: string
  description: string
  date: string
  amount: number
  service: string
}

export interface UserProfile {
  id: string
  email: string
  displayName: string
  organization: string
  createdAt: string
  twoFactorEnabled: boolean
}

export interface NotificationSetting {
  id: string
  label: string
  description: string
  enabled: boolean
}