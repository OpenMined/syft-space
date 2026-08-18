import { apiClient } from '../client'
import type { FeedbackResponse } from '../types'

export const feedbackApi = {
  submit: async (data: {
    category: string
    description: string
    page_url?: string
    app_version?: string
    browser_info?: string
    screenshot?: Blob | null
  }): Promise<FeedbackResponse> => {
    const formData = new FormData()
    formData.append('category', data.category)
    formData.append('description', data.description)
    if (data.page_url) formData.append('page_url', data.page_url)
    if (data.app_version) formData.append('app_version', data.app_version)
    if (data.browser_info) formData.append('browser_info', data.browser_info)
    if (data.screenshot) formData.append('screenshot', data.screenshot, 'screenshot.png')

    const response = await apiClient.post('/feedback', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return response.data
  },
}
