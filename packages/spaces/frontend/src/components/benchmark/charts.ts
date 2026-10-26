/** Shared chart styling: fixed 0–100 share axes and one colour per meaning. */
import type { TooltipItem } from 'chart.js'

/** Muted grey, legible on both themes. */
const AXIS_COLOR = '#9ca3af'

export const CHART_COLORS = {
  /** Answer outcomes. */
  correct: '#10b981',
  abstain: AXIS_COLOR,
  hallucinate: '#ef4444',
  incomplete: '#8b5cf6',
  /** Model bars and question-kind bars. */
  model: '#3b82f6',
  skill: '#2dd4bf',
  /** The same model without data; a lighter shade of `model`. */
  alone: '#93c5fd',
  /** Held under push-back, and stable across temperatures. */
  held: '#a78bfa',
  temperature: '#f59e0b',
} as const

const PCT_TICKS = {
  color: AXIS_COLOR,
  font: { size: 11 },
  callback: (value: string | number) => `${value}%`,
}

const GRID = { color: 'rgba(255,255,255,0.08)' }

const LABEL_TICKS = { color: AXIS_COLOR, font: { size: 11 } }

/** Horizontal share bars on a fixed 0–100 axis; the legend only for several series. */
export function pctBarOptions(legend = false) {
  return {
    indexAxis: 'y' as const,
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        display: legend,
        labels: { color: AXIS_COLOR, boxWidth: 10, font: { size: 11 } },
      },
      tooltip: {
        callbacks: { label: (ctx: TooltipItem<'bar'>) => `${ctx.parsed.x}%` },
      },
    },
    scales: {
      x: { min: 0, max: 100, ticks: PCT_TICKS, grid: GRID, border: { display: false } },
      y: { ticks: LABEL_TICKS, grid: { display: false }, border: { display: false } },
    },
  }
}

/** Container height for a horizontal bar chart; Chart.js does not size it by row count. */
export function barChartHeight(rows: number): number {
  return Math.max(120, rows * 32)
}
