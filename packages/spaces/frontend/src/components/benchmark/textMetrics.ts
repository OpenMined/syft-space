/** BLEU / ROUGE / BERTScore in words, for the technical view. */
import type { BenchmarkTextMetricsRow, BenchmarkTextScores } from '@/api/types'

/** Display order and names. */
export const TEXT_METRIC_LABEL: Record<string, string> = {
  bleu: 'BLEU',
  rouge1_f: 'ROUGE-1',
  rouge2_f: 'ROUGE-2',
  rougeL_f: 'ROUGE-L',
  bertscore_f1: 'BERTScore',
}

export interface MetricPart {
  key: string
  label: string
  value: string
}

/** The scores present, in display order, two decimals; [] for none. */
export function metricParts(scores: BenchmarkTextScores | null | undefined): MetricPart[] {
  if (!scores) return []
  const known = Object.keys(TEXT_METRIC_LABEL)
  const keys = [
    ...known.filter((k) => k in scores),
    ...Object.keys(scores).filter((k) => !known.includes(k)),
  ]
  return keys.flatMap((key) => {
    const value = (scores as Record<string, number | undefined>)[key]
    if (typeof value !== 'number' || !Number.isFinite(value)) return []
    return [{ key, label: TEXT_METRIC_LABEL[key] ?? key, value: value.toFixed(2) }]
  })
}

/** `BLEU 0.31 · ROUGE-L 0.48`; empty for none. */
export function metricsLine(scores: BenchmarkTextScores | null | undefined): string {
  return metricParts(scores)
    .map((p) => `${p.label} ${p.value}`)
    .join(' · ')
}

/** The metric columns a summary table needs: those any row has, in display order. */
export function metricColumns(rows: BenchmarkTextMetricsRow[]): string[] {
  const seen = new Set(rows.flatMap((r) => Object.keys(r.scores ?? {})))
  const known = Object.keys(TEXT_METRIC_LABEL)
  return [...known.filter((k) => seen.has(k)), ...[...seen].filter((k) => !known.includes(k))]
}

/** One score cell, two decimals; a dash when the row lacks it. */
export function metricCell(row: BenchmarkTextMetricsRow, key: string): string {
  const value = (row.scores as Record<string, number | undefined>)[key]
  return typeof value === 'number' && Number.isFinite(value) ? value.toFixed(2) : '—'
}
