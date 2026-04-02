/**
 * Canvas-based word cloud renderer with spiral placement.
 *
 * Words are placed using an Archimedean spiral from the center outward,
 * with random rotation for visual variety. No external dependencies.
 */

import type { WordCloudEntry } from '@/api/types/analytics'

export interface WordCloudConfig {
  colors?: string[]
  fontFamily?: string
  rotateChance?: number
  minFontSize?: number
  maxFontSize?: number
}

const DEFAULT_COLORS = [
  '#10b981',
  '#3b82f6',
  '#8b5cf6',
  '#ec4899',
  '#f59e0b',
  '#14b8a6',
  '#ef4444',
  '#6366f1',
]

const DEFAULT_CONFIG: Required<WordCloudConfig> = {
  colors: DEFAULT_COLORS,
  fontFamily: 'Inter, system-ui, sans-serif',
  rotateChance: 0.3,
  minFontSize: 12,
  maxFontSize: 56,
}

interface PlacedWord {
  text: string
  x: number
  y: number
  fontSize: number
  color: string
  rotate: boolean
  width: number
  height: number
}

function overlaps(a: PlacedWord, b: PlacedWord): boolean {
  const ax = a.rotate ? a.x - a.height / 2 : a.x - a.width / 2
  const ay = a.rotate ? a.y - a.width / 2 : a.y - a.height / 2
  const aw = a.rotate ? a.height : a.width
  const ah = a.rotate ? a.width : a.height

  const bx = b.rotate ? b.x - b.height / 2 : b.x - b.width / 2
  const by = b.rotate ? b.y - b.width / 2 : b.y - b.height / 2
  const bw = b.rotate ? b.height : b.width
  const bh = b.rotate ? b.width : b.height

  return ax < bx + bw && ax + aw > bx && ay < by + bh && ay + ah > by
}

function inBounds(w: PlacedWord, canvasW: number, canvasH: number): boolean {
  const halfW = (w.rotate ? w.height : w.width) / 2
  const halfH = (w.rotate ? w.width : w.height) / 2
  return (
    w.x - halfW >= 0 &&
    w.x + halfW <= canvasW &&
    w.y - halfH >= 0 &&
    w.y + halfH <= canvasH
  )
}

export function renderWordCloud(
  canvas: HTMLCanvasElement,
  words: WordCloudEntry[],
  userConfig?: WordCloudConfig,
): void {
  const config = { ...DEFAULT_CONFIG, ...userConfig }
  const ctx = canvas.getContext('2d')
  if (!ctx || words.length === 0) return

  const rect = canvas.getBoundingClientRect()
  const dpr = window.devicePixelRatio || 1
  canvas.width = rect.width * dpr
  canvas.height = rect.height * dpr
  ctx.scale(dpr, dpr)

  const W = rect.width
  const H = rect.height
  const centerX = W / 2
  const centerY = H / 2

  ctx.clearRect(0, 0, W, H)

  const maxCount = words[0]?.count ?? 1
  const minCount = words[words.length - 1]?.count ?? 1
  const countRange = Math.max(maxCount - minCount, 1)

  // Sort by count descending, randomize order within same count
  const shuffled = [...words].sort((a, b) => b.count - a.count || Math.random() - 0.5)

  const placed: PlacedWord[] = []

  for (const entry of shuffled) {
    const ratio = (entry.count - minCount) / countRange
    const fontSize = config.minFontSize + ratio * (config.maxFontSize - config.minFontSize)
    const rotate = Math.random() < config.rotateChance
    const color =
      config.colors[Math.floor(Math.random() * config.colors.length)] ?? '#10b981'

    ctx.font = `bold ${fontSize}px ${config.fontFamily}`
    const metrics = ctx.measureText(entry.word)
    const textWidth = metrics.width + 4
    const textHeight = fontSize * 1.2

    // Spiral placement: try positions along an Archimedean spiral
    let wordPlaced = false
    for (let t = 0; t < 1500; t++) {
      const angle = t * 0.15
      const radius = 2 + t * 0.4
      const x = centerX + radius * Math.cos(angle)
      const y = centerY + radius * Math.sin(angle)

      const candidate: PlacedWord = {
        text: entry.word,
        x,
        y,
        fontSize,
        color,
        rotate,
        width: textWidth,
        height: textHeight,
      }

      if (!inBounds(candidate, W, H)) continue
      if (placed.some((p) => overlaps(candidate, p))) continue

      placed.push(candidate)

      // Draw immediately after placement
      ctx.save()
      ctx.translate(candidate.x, candidate.y)
      if (candidate.rotate) ctx.rotate(-Math.PI / 2)
      ctx.font = `bold ${candidate.fontSize}px ${config.fontFamily}`
      ctx.fillStyle = candidate.color
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      ctx.fillText(candidate.text, 0, 0)
      ctx.restore()

      wordPlaced = true
      break
    }

    if (!wordPlaced) continue
  }
}
