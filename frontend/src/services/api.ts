import type { Service, Message, Transaction, UserProfile } from '../types'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:3000/api'

class ApiService {
  private async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
    })

    if (!response.ok) {
      throw new Error(`API Error: ${response.statusText}`)
    }

    return response.json()
  }

  // Services
  async getServices(): Promise<Service[]> {
    return this.request<Service[]>('/services')
  }

  async getService(id: string): Promise<Service> {
    return this.request<Service>(`/services/${id}`)
  }

  async createService(service: Partial<Service>): Promise<Service> {
    return this.request<Service>('/services', {
      method: 'POST',
      body: JSON.stringify(service),
    })
  }

  async updateService(id: string, updates: Partial<Service>): Promise<Service> {
    return this.request<Service>(`/services/${id}`, {
      method: 'PUT',
      body: JSON.stringify(updates),
    })
  }

  async deleteService(id: string): Promise<void> {
    await this.request(`/services/${id}`, {
      method: 'DELETE',
    })
  }

  // Messages/Inbox
  async getMessages(): Promise<Message[]> {
    return this.request<Message[]>('/messages')
  }

  async markMessageAsRead(id: string): Promise<void> {
    await this.request(`/messages/${id}/read`, {
      method: 'POST',
    })
  }

  async markAllMessagesAsRead(): Promise<void> {
    await this.request('/messages/read-all', {
      method: 'POST',
    })
  }

  // Usage and Billing
  async getUsageStats(): Promise<{
    currentBalance: number
    monthlyUsage: number
    usageChange: number
    computeHours: number
    storageGB: number
    apiCalls: number
  }> {
    return this.request('/usage/stats')
  }

  async getTransactions(): Promise<Transaction[]> {
    return this.request<Transaction[]>('/transactions')
  }

  async addFunds(amount: number): Promise<void> {
    await this.request('/billing/add-funds', {
      method: 'POST',
      body: JSON.stringify({ amount }),
    })
  }

  // User Profile
  async getProfile(): Promise<UserProfile> {
    return this.request<UserProfile>('/user/profile')
  }

  async updateProfile(updates: Partial<UserProfile>): Promise<UserProfile> {
    return this.request<UserProfile>('/user/profile', {
      method: 'PUT',
      body: JSON.stringify(updates),
    })
  }

  async changePassword(currentPassword: string, newPassword: string): Promise<void> {
    await this.request('/user/change-password', {
      method: 'POST',
      body: JSON.stringify({ currentPassword, newPassword }),
    })
  }

  // API Keys
  async getApiKeys(): Promise<Array<{ id: string; name: string; lastUsed: string }>> {
    return this.request('/user/api-keys')
  }

  async createApiKey(name: string): Promise<{ id: string; key: string }> {
    return this.request('/user/api-keys', {
      method: 'POST',
      body: JSON.stringify({ name }),
    })
  }

  async deleteApiKey(id: string): Promise<void> {
    await this.request(`/user/api-keys/${id}`, {
      method: 'DELETE',
    })
  }
}

export const apiService = new ApiService()
export default apiService