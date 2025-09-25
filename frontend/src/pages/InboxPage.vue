<script setup lang="ts">
import { ref, computed } from 'vue'
import { Inbox, X, Check, AlertCircle, Info, Trash2, Users, Gauge, Calculator, Activity } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'

interface InboxItem {
  id: string
  source: string
  title: string
  summary: string
  longDescription: string
  timestamp: Date
  read: boolean
  dismissed: boolean
  actions?: {
    positive?: {
      label: string
      handler: () => void
    }
    negative?: {
      label: string
      handler: () => void
    }
  }
}

const inboxItems = ref<InboxItem[]>([
  {
    id: '1',
    source: 'Human-in-the-Loop Policy',
    title: 'Request from user@openmined.org',
    summary: 'What is Network Sourced AI?',
    longDescription: `## Request Details

**User:** user@openmined.org  
**Time:** ${new Date().toLocaleString()}

### Query
What is Network Sourced AI?

### Response
Network Sourced AI refers to a paradigm where AI models and computations are distributed across a network of participants rather than being centralized in a single location. This approach enables:

1. **Privacy-Preserving AI**: Data remains with its owners while models learn from it
2. **Federated Learning**: Models are trained across decentralized data sources
3. **Collaborative Intelligence**: Multiple parties contribute to AI development without sharing raw data
4. **Democratized Access**: Broader participation in AI development and deployment

This technology is particularly valuable for sensitive domains like healthcare, finance, and personal data applications where privacy and data sovereignty are paramount.`,
    timestamp: new Date(Date.now() - 1000 * 60 * 5),
    read: false,
    dismissed: false,
    actions: {
      positive: {
        label: 'Approve',
        handler: () => console.log('Approved request 1')
      },
      negative: {
        label: 'Reject',
        handler: () => console.log('Rejected request 1')
      }
    }
  },
  {
    id: '2',
    source: 'Human-in-the-Loop Policy',
    title: 'Request from alice.chen@research.edu',
    summary: 'How does federated learning protect privacy?',
    longDescription: `## Request Details

**User:** alice.chen@research.edu  
**Time:** ${new Date(Date.now() - 1000 * 60 * 15).toLocaleString()}

### Query
How does federated learning protect privacy?

### Response
Federated learning protects privacy through several key mechanisms:

1. **Local Data Storage**: Training data never leaves the user's device or local server
2. **Gradient Aggregation**: Only model updates (gradients) are shared, not raw data
3. **Differential Privacy**: Noise is added to updates to prevent data reconstruction
4. **Secure Aggregation**: Cryptographic techniques ensure individual updates remain private
5. **Homomorphic Encryption**: Enables computation on encrypted data

These techniques work together to enable collaborative model training while maintaining strong privacy guarantees for individual participants.`,
    timestamp: new Date(Date.now() - 1000 * 60 * 15),
    read: true,
    dismissed: false,
    actions: {
      positive: {
        label: 'Approve',
        handler: () => console.log('Approved request 2')
      },
      negative: {
        label: 'Reject',
        handler: () => console.log('Rejected request 2')
      }
    }
  },
  {
    id: '3',
    source: 'System Update',
    title: 'New version available',
    summary: 'SyftAI Server v2.1.0 is now available with performance improvements',
    longDescription: `## Update Available: SyftAI Server v2.1.0

### What's New
- **Performance**: 30% faster model inference
- **Security**: Enhanced encryption for data in transit
- **Features**: New batch processing capabilities
- **Bug Fixes**: Resolved 15 known issues

### Breaking Changes
None in this release.

### Update Instructions
Run the following command to update:
\`\`\`bash
syftai update --version 2.1.0
\`\`\`

Or use the automatic updater in Settings > General.`,
    timestamp: new Date(Date.now() - 1000 * 60 * 60),
    read: false,
    dismissed: false,
    actions: {
      positive: {
        label: 'Update Now',
        handler: () => console.log('Starting update')
      }
    }
  },
  {
    id: '4',
    source: 'Human-in-the-Loop Policy',
    title: 'Request from bob.smith@fintech.com',
    summary: 'Can you explain homomorphic encryption?',
    longDescription: `## Request Details

**User:** bob.smith@fintech.com  
**Time:** ${new Date(Date.now() - 1000 * 60 * 60 * 2).toLocaleString()}

### Query
Can you explain homomorphic encryption?

### Response
Homomorphic encryption is a revolutionary cryptographic technique that allows computations to be performed on encrypted data without decrypting it first. Key aspects include:

1. **Full Homomorphism**: Supports both addition and multiplication on encrypted data
2. **Privacy Preservation**: Data remains encrypted throughout computation
3. **Cloud Computing**: Enables secure outsourcing of computation
4. **Financial Applications**: Critical for privacy-preserving financial analytics

While computationally intensive, recent advances have made it increasingly practical for real-world applications, particularly in finance and healthcare.`,
    timestamp: new Date(Date.now() - 1000 * 60 * 60 * 2),
    read: false,
    dismissed: false,
    actions: {
      positive: {
        label: 'Approve',
        handler: () => console.log('Approved request 4')
      },
      negative: {
        label: 'Reject',
        handler: () => console.log('Rejected request 4')
      }
    }
  },
  {
    id: '5',
    source: 'Security Alert',
    title: 'Unusual activity detected',
    summary: '5 failed authentication attempts from IP 192.168.1.100',
    longDescription: `## Security Alert

### Summary
We detected unusual authentication activity on your account.

### Details
- **Failed Attempts**: 5
- **Source IP**: 192.168.1.100
- **Location**: Unknown
- **Time Period**: Last 30 minutes
- **User Agent**: Mozilla/5.0 (Windows NT 10.0; Win64; x64)

### Recommended Actions
1. Review your recent login activity
2. Change your password if you don't recognize this activity
3. Enable two-factor authentication for added security
4. Check for any unauthorized API key usage

This could be a brute force attack attempt. Your account has been temporarily locked for security.`,
    timestamp: new Date(Date.now() - 1000 * 60 * 60 * 3),
    read: true,
    dismissed: false,
    actions: {
      negative: {
        label: 'Dismiss Alert',
        handler: () => console.log('Dismissed security alert')
      }
    }
  },
  {
    id: '6',
    source: 'Human-in-the-Loop Policy',
    title: 'Request from sarah.johnson@healthcare.org',
    summary: 'What are the HIPAA implications of federated learning?',
    longDescription: `## Request Details

**User:** sarah.johnson@healthcare.org  
**Time:** ${new Date(Date.now() - 1000 * 60 * 60 * 24).toLocaleString()}

### Query
What are the HIPAA implications of federated learning?

### Response
Federated learning offers several advantages for HIPAA compliance:

1. **Data Minimization**: PHI never leaves the covered entity's systems
2. **Access Controls**: Maintains existing security infrastructure
3. **Audit Trails**: All model training activities are logged locally
4. **Business Associates**: Reduced need for BAAs as data isn't shared

However, considerations include:
- Model updates could potentially leak information
- Differential privacy parameters must be carefully chosen
- Security of the aggregation server is critical
- Documentation requirements for the federated learning process

Overall, federated learning can enhance HIPAA compliance when properly implemented.`,
    timestamp: new Date(Date.now() - 1000 * 60 * 60 * 24),
    read: false,
    dismissed: false,
    actions: {
      positive: {
        label: 'Approve',
        handler: () => console.log('Approved request 6')
      },
      negative: {
        label: 'Reject',
        handler: () => console.log('Rejected request 6')
      }
    }
  },
  {
    id: '7',
    source: 'Service Status',
    title: 'Vector database maintenance completed',
    summary: 'Weaviate database has been successfully optimized',
    longDescription: `## Maintenance Report

### Summary
The scheduled maintenance for your Weaviate vector database has been completed successfully.

### Actions Performed
- Index optimization completed
- Garbage collection executed
- Performance metrics reset
- Backup created before maintenance

### Results
- **Storage Saved**: 2.3 GB
- **Query Performance**: +15% improvement
- **Index Size**: Reduced by 18%
- **Downtime**: 0 minutes (online maintenance)

No action required from your end. All services are operating normally.`,
    timestamp: new Date(Date.now() - 1000 * 60 * 60 * 48),
    read: true,
    dismissed: false
  },
  {
    id: '8',
    source: 'Usage Alert',
    title: 'Monthly API limit approaching',
    summary: 'You have used 85% of your monthly API quota',
    longDescription: `## API Usage Alert

### Current Usage
- **Used**: 850,000 requests
- **Limit**: 1,000,000 requests
- **Remaining**: 150,000 requests
- **Days Left**: 5

### Top Consumers
1. Legal Document Analysis Service: 45%
2. Customer Insights Engine: 30%
3. Research Assistant: 15%
4. Other: 10%

### Recommendations
Consider upgrading your plan or optimizing your API usage patterns to avoid service interruption.`,
    timestamp: new Date(Date.now() - 1000 * 60 * 60 * 72),
    read: false,
    dismissed: false,
    actions: {
      positive: {
        label: 'Upgrade Plan',
        handler: () => console.log('Navigating to billing')
      }
    }
  }
])

const selectedItem = ref<InboxItem | null>(null)
const dialogOpen = ref(false)

const activeItems = computed(() => 
  inboxItems.value.filter(item => !item.dismissed).sort((a, b) => b.timestamp.getTime() - a.timestamp.getTime())
)

const unreadCount = computed(() => 
  activeItems.value.filter(item => !item.read).length
)

const openItemDialog = (item: InboxItem) => {
  selectedItem.value = item
  dialogOpen.value = true
  if (!item.read) {
    item.read = true
  }
}

const dismissItem = (item: InboxItem) => {
  item.dismissed = true
  if (selectedItem.value?.id === item.id) {
    dialogOpen.value = false
  }
}

const handlePositiveAction = (item: InboxItem) => {
  if (item.actions?.positive?.handler) {
    item.actions.positive.handler()
  }
  dismissItem(item)
}

const handleNegativeAction = (item: InboxItem) => {
  if (item.actions?.negative?.handler) {
    item.actions.negative.handler()
  }
  dismissItem(item)
}

const getSourceIcon = (source: string) => {
  // Policy-specific icons
  if (source === 'Human-in-the-Loop Policy') return Users
  if (source.includes('Rate Limiting')) return Gauge
  if (source === 'Accounting Policy') return Calculator
  if (source === 'OpenTelemetry Observability Policy') return Activity
  
  // Other source icons
  if (source.includes('Security')) return AlertCircle
  return Info
}

const getSourceColor = (source: string) => {
  // Policy-specific colors
  if (source === 'Human-in-the-Loop Policy') return 'text-orange-600 bg-orange-100'
  if (source.includes('Rate Limiting')) return 'text-blue-600 bg-blue-100'
  if (source === 'Accounting Policy') return 'text-green-600 bg-green-100'
  if (source === 'OpenTelemetry Observability Policy') return 'text-purple-600 bg-purple-100'
  
  // Other source colors
  if (source.includes('Security')) return 'text-red-600 bg-red-100'
  if (source.includes('Update')) return 'text-blue-600 bg-blue-100'
  if (source.includes('Usage')) return 'text-purple-600 bg-purple-100'
  return 'text-gray-600 bg-gray-100'
}

const formatTimestamp = (date: Date) => {
  const now = new Date()
  const diff = now.getTime() - date.getTime()
  const minutes = Math.floor(diff / 60000)
  const hours = Math.floor(diff / 3600000)
  const days = Math.floor(diff / 86400000)
  
  if (minutes < 1) return 'Just now'
  if (minutes < 60) return `${minutes} minute${minutes > 1 ? 's' : ''} ago`
  if (hours < 24) return `${hours} hour${hours > 1 ? 's' : ''} ago`
  if (days < 7) return `${days} day${days > 1 ? 's' : ''} ago`
  
  return date.toLocaleDateString('en-US', { 
    month: 'short', 
    day: 'numeric', 
    year: date.getFullYear() !== now.getFullYear() ? 'numeric' : undefined 
  })
}
</script>

<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <!-- Header -->
    <div class="flex items-center justify-between mb-8">
      <div class="flex items-center gap-3">
        <Inbox class="h-6 w-6 text-gray-600" />
        <h1 class="text-2xl font-semibold text-gray-900">Inbox</h1>
        <Badge v-if="unreadCount > 0" variant="secondary" class="bg-purple-100 text-purple-700">
          {{ unreadCount }} new
        </Badge>
      </div>
    </div>

    <!-- Empty State -->
    <div v-if="activeItems.length === 0" class="text-center py-12">
      <Inbox class="mx-auto h-12 w-12 text-gray-400" />
      <h3 class="mt-2 text-sm font-semibold text-gray-900">No items</h3>
      <p class="mt-1 text-sm text-gray-500">Your inbox is empty.</p>
    </div>

    <!-- Inbox Items -->
    <div v-else class="space-y-4">
      <Card
        v-for="item in activeItems"
        :key="item.id"
        class="cursor-pointer hover:shadow-md transition-shadow"
        :class="{ 'border-purple-200 bg-purple-50/50': !item.read }"
        @click="openItemDialog(item)"
      >
        <CardHeader class="pb-3">
          <div class="flex items-start justify-between gap-4">
            <div class="flex items-start gap-3 flex-1">
              <div :class="`p-2 rounded-lg ${getSourceColor(item.source)}`">
                <component :is="getSourceIcon(item.source)" class="h-4 w-4" />
              </div>
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2 mb-1">
                  <Badge variant="outline" class="text-xs">{{ item.source }}</Badge>
                  <span class="text-xs text-gray-500">
                    {{ item.timestamp.toLocaleString() }}
                  </span>
                  <div v-if="!item.read" class="w-2 h-2 bg-purple-500 rounded-full"></div>
                </div>
                <CardTitle class="text-base">{{ item.title }}</CardTitle>
                <CardDescription class="mt-1">{{ item.summary }}</CardDescription>
              </div>
            </div>
            <div class="flex items-center gap-2">
              <!-- Action Buttons -->
              <div v-if="item.actions" class="flex items-center gap-2">
                <Button
                  v-if="item.actions.positive"
                  size="sm"
                  variant="default"
                  class="h-8 text-xs"
                  @click.stop="handlePositiveAction(item)"
                >
                  {{ item.actions.positive.label }}
                </Button>
                <Button
                  v-if="item.actions.negative"
                  size="sm"
                  variant="outline"
                  class="h-8 text-xs"
                  @click.stop="handleNegativeAction(item)"
                >
                  {{ item.actions.negative.label }}
                </Button>
              </div>
              <!-- Dismiss Button -->
              <Button
                variant="ghost"
                size="sm"
                class="h-8 w-8 p-0 ml-2"
                @click.stop="dismissItem(item)"
              >
                <X class="h-4 w-4" />
              </Button>
            </div>
          </div>
        </CardHeader>
      </Card>
    </div>

    <!-- Item Detail Dialog -->
    <Dialog v-model:open="dialogOpen">
      <DialogContent v-if="selectedItem" class="max-w-5xl max-h-[90vh] flex flex-col p-0 overflow-hidden sm:max-w-5xl">
        <!-- Header with background -->
        <div class="flex-shrink-0 border-b bg-gray-50">
          <DialogHeader class="p-6 pb-4">
            <div class="flex items-start justify-between mb-3">
              <div class="flex items-center gap-3">
                <div :class="`p-3 rounded-lg ${getSourceColor(selectedItem.source)}`">
                  <component :is="getSourceIcon(selectedItem.source)" class="h-5 w-5" />
                </div>
                <div>
                  <div class="flex items-center gap-2 mb-1">
                    <Badge variant="outline" class="text-xs">{{ selectedItem.source }}</Badge>
                    <div v-if="!selectedItem.read" class="flex items-center gap-1 text-xs text-purple-600">
                      <div class="w-2 h-2 bg-purple-500 rounded-full"></div>
                      <span>New</span>
                    </div>
                  </div>
                  <span class="text-sm text-gray-500">
                    {{ formatTimestamp(selectedItem.timestamp) }}
                  </span>
                </div>
              </div>
            </div>
            <DialogTitle class="text-xl font-semibold">{{ selectedItem.title }}</DialogTitle>
            <DialogDescription class="mt-2 text-base">{{ selectedItem.summary }}</DialogDescription>
          </DialogHeader>
        </div>
        
        <!-- Content -->
        <div class="flex-1 min-h-0 overflow-y-auto">
          <div class="p-6">
            <div class="prose prose-sm max-w-none prose-headings:font-semibold prose-h2:text-lg prose-h3:text-base prose-p:text-gray-600 prose-strong:text-gray-900 prose-code:text-purple-600 prose-pre:bg-gray-50 prose-pre:border prose-li:text-gray-600" v-html="markdownToHtml(selectedItem.longDescription)" />
          </div>
        </div>
        
        <!-- Footer with actions -->
        <div class="flex-shrink-0 border-t bg-gray-50">
          <DialogFooter class="p-6 pt-4">
            <div class="flex items-center justify-between w-full">
              <div class="flex items-center gap-4">
                <Button
                  variant="ghost"
                  size="default"
                  class="text-gray-600 hover:text-gray-900"
                  @click="dismissItem(selectedItem); dialogOpen = false"
                >
                  <Trash2 class="h-4 w-4 mr-2" />
                  Dismiss
                </Button>
              </div>
              <div class="flex items-center gap-3">
                <Button
                  v-if="selectedItem.actions?.negative"
                  variant="outline"
                  size="default"
                  @click="handleNegativeAction(selectedItem)"
                >
                  {{ selectedItem.actions.negative.label }}
                </Button>
                <Button
                  v-if="selectedItem.actions?.positive"
                  variant="default"
                  size="default"
                  class="bg-purple-600 hover:bg-purple-700"
                  @click="handlePositiveAction(selectedItem)"
                >
                  {{ selectedItem.actions.positive.label }}
                </Button>
              </div>
            </div>
          </DialogFooter>
        </div>
      </DialogContent>
    </Dialog>
  </div>
</template>

<script lang="ts">
// Enhanced markdown to HTML converter
function markdownToHtml(markdown: string): string {
  let html = markdown
    // Headers
    .replace(/^### (.*$)/gim, '<h3>$1</h3>')
    .replace(/^## (.*$)/gim, '<h2>$1</h2>')
    .replace(/^# (.*$)/gim, '<h1>$1</h1>')
    
    // Bold and italic
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/\*([^*]+)\*/g, '<em>$1</em>')
    
    // Code blocks with language hint
    .replace(/```(\w+)?\n([^`]+)```/g, '<pre><code>$2</code></pre>')
    .replace(/```([^`]+)```/g, '<pre><code>$1</code></pre>')
    
    // Inline code
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    
    // Links
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" class="text-purple-600 hover:text-purple-700 underline">$1</a>')
    
    // Line breaks
    .replace(/\n\n/g, '</p><p>')
    
    // Lists - handle multi-line
    .split('\n')
    .map(line => {
      if (/^\d+\.\s/.test(line)) {
        return '<li>' + line.substring(line.indexOf('.') + 2) + '</li>'
      } else if (/^-\s/.test(line)) {
        return '<li>' + line.substring(2) + '</li>'
      }
      return line
    })
    .join('\n')
    
  // Wrap in paragraph tags
  html = '<p>' + html + '</p>'
  
  // Clean up empty paragraphs
  html = html.replace(/<p>\s*<\/p>/g, '')
  
  // Wrap consecutive list items in ul/ol tags
  html = html.replace(/(<li>.*<\/li>\n?)+/g, match => {
    if (match.includes('<li>1.')) {
      return '<ol class="list-decimal list-inside space-y-1">' + match + '</ol>'
    }
    return '<ul class="list-disc list-inside space-y-1">' + match + '</ul>'
  })
  
  return html
}
</script>