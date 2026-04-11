import {
  Activity,
  AlertCircle,
  Calculator,
  Gauge,
  Info,
  Users,
  type LucideIcon,
} from 'lucide-vue-next'

export const getInboxSourceIcon = (source: string): LucideIcon => {
  if (source === 'Human-in-the-Loop Policy') return Users
  if (source.includes('Rate Limiting')) return Gauge
  if (source === 'Accounting Policy') return Calculator
  if (source === 'OpenTelemetry Observability Policy') return Activity
  if (source.includes('Security')) return AlertCircle
  return Info
}

export const getInboxSourceColor = (source: string): string => {
  if (source === 'Human-in-the-Loop Policy')
    return 'text-orange-600 dark:text-orange-400 bg-orange-50 dark:bg-orange-950/50'
  if (source.includes('Rate Limiting'))
    return 'text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-950/50'
  if (source === 'Accounting Policy')
    return 'text-green-600 dark:text-green-400 bg-green-50 dark:bg-green-950/50'
  if (source === 'OpenTelemetry Observability Policy') return 'text-primary bg-primary/10'
  if (source.includes('Security')) return 'text-destructive bg-destructive/10'
  if (source.includes('Update'))
    return 'text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-950/50'
  if (source.includes('Usage')) return 'text-primary bg-primary/10'
  return 'text-muted-foreground bg-muted'
}

