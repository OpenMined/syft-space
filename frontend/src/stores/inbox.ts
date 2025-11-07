import { ref, computed } from 'vue'
import { defineStore } from 'pinia'

export interface InboxItem {
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

export const useInboxStore = defineStore('inbox', () => {
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
          handler: () => console.log('Approved request 1'),
        },
        negative: {
          label: 'Reject',
          handler: () => console.log('Rejected request 1'),
        },
      },
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
          handler: () => console.log('Approved request 2'),
        },
        negative: {
          label: 'Reject',
          handler: () => console.log('Rejected request 2'),
        },
      },
    },
    {
      id: '3',
      source: 'System Update',
      title: 'New version available',
      summary: 'Syft AI Space v2.1.0 is now available with performance improvements',
      longDescription: `## Update Available: Syft AI Space v2.1.0

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
          handler: () => console.log('Starting update'),
        },
      },
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
          handler: () => console.log('Approved request 4'),
        },
        negative: {
          label: 'Reject',
          handler: () => console.log('Rejected request 4'),
        },
      },
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
          handler: () => console.log('Dismissed security alert'),
        },
      },
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
          handler: () => console.log('Approved request 6'),
        },
        negative: {
          label: 'Reject',
          handler: () => console.log('Rejected request 6'),
        },
      },
    },
    {
      id: '7',
      source: 'Endpoint Status',
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

No action required from your end. All endpoints are operating normally.`,
      timestamp: new Date(Date.now() - 1000 * 60 * 60 * 48),
      read: true,
      dismissed: false,
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
1. Legal Document Analysis Endpoint: 45%
2. Customer Insights Engine: 30%
3. Research Assistant: 15%
4. Other: 10%

### Recommendations
Consider upgrading your plan or optimizing your API usage patterns to avoid interruption.`,
      timestamp: new Date(Date.now() - 1000 * 60 * 60 * 72),
      read: false,
      dismissed: false,
      actions: {
        positive: {
          label: 'Upgrade Plan',
          handler: () => console.log('Navigating to billing'),
        },
      },
    },
  ])

  const activeItems = computed(() => {
    return inboxItems.value
      .filter((item) => !item.dismissed)
      .sort((a, b) => b.timestamp.getTime() - a.timestamp.getTime())
  })

  const unreadCount = computed(() => activeItems.value.filter((item) => !item.read).length)

  const markAsRead = (itemId: string) => {
    const item = inboxItems.value.find((item) => item.id === itemId)
    if (item) {
      item.read = true
    }
  }

  const dismissItem = (itemId: string) => {
    const item = inboxItems.value.find((item) => item.id === itemId)
    if (item) {
      item.dismissed = true
    }
  }

  return {
    inboxItems,
    activeItems,
    unreadCount,
    markAsRead,
    dismissItem,
  }
})
