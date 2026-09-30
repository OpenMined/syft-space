/**
 * One look for every benchmark chart, in one place.
 *
 * The report block and the results tab draw the same figures, and a share
 * drawn on a 0-100 axis in one place and on an auto-scaled one in the other
 * reads as two different numbers. So the axis, the tick words and the colours
 * live here rather than in each component: an accuracy bar always runs the
 * full 0-100, and "correct" is the same green wherever it is drawn.
 */
import type { TooltipItem } from 'chart.js'

/** Muted grey that stays legible on both themes — the charts have no theme of their own. */
const AXIS_COLOR = '#9ca3af'

export const CHART_COLORS = {
  /** The answer broke down as: correct, abstained, invented. */
  correct: '#10b981',
  abstain: AXIS_COLOR,
  hallucinate: '#ef4444',
  /** A model under test, and a type of question — distinct, never compared to each other. */
  model: '#3b82f6',
  skill: '#2dd4bf',
  /** The same model with nothing in front of it — paired against `model`, so a shade of it. */
  alone: '#93c5fd',
  /** What survived being argued with, and what survived a rising temperature. */
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

/**
 * Horizontal bars of shares: always the whole 0-100, never auto-scaled.
 *
 * The legend is off unless a chart draws more than one series — with a single
 * series it only repeats the title above it.
 */
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

/** A share over time: the same full axis, so a run cannot look better by being drawn alone. */
export function pctLineOptions() {
  return {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: true, labels: { color: AXIS_COLOR, boxWidth: 10, font: { size: 11 } } },
      tooltip: {
        callbacks: {
          label: (ctx: TooltipItem<'line'>) => `${ctx.dataset.label}: ${ctx.parsed.y}%`,
        },
      },
    },
    scales: {
      x: { ticks: LABEL_TICKS, grid: { display: false }, border: { display: false } },
      y: { min: 0, max: 100, ticks: PCT_TICKS, grid: GRID, border: { display: false } },
    },
  }
}

/**
 * Chart.js takes a horizontal bar chart's height from its container, not from
 * how many rows it has — without this, nine models draw as nine slivers in the
 * box that fitted three.
 */
export function barChartHeight(rows: number): number {
  return Math.max(120, rows * 32)
}
