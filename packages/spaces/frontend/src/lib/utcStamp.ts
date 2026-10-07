/**
 * Helpers for folder names stamped with a UTC moment, e.g. the news
 * collector's run folders `2026-10-07_1900_UTC` (optionally suffixed `_2`,
 * `_3`, ... on collision). The UI shows the same moment in the viewer's time
 * zone next to such names.
 */

const UTC_STAMP_RE = /^(\d{4})-(\d{2})-(\d{2})_(\d{2})(\d{2})_UTC(?:_[1-9]\d*)?$/

/** Parse a `YYYY-MM-DD_HHMM_UTC[_N]` name; null for anything else or an impossible date. */
export function parseUtcStamp(name: string): Date | null {
  const m = UTC_STAMP_RE.exec(name)
  if (!m) return null
  const [year, month, day, hour, minute] = m.slice(1).map(Number) as [
    number,
    number,
    number,
    number,
    number,
  ]
  const date = new Date(Date.UTC(year, month - 1, day, hour, minute))
  // Date.UTC rolls over out-of-range parts (month 13, minute 99); reject those.
  if (
    date.getUTCFullYear() !== year ||
    date.getUTCMonth() !== month - 1 ||
    date.getUTCDate() !== day ||
    date.getUTCHours() !== hour ||
    date.getUTCMinutes() !== minute
  ) {
    return null
  }
  return date
}

/** The deepest UTC-stamped segment of a `/`-separated path, parsed; null if none. */
export function findUtcStampInPath(path: string): Date | null {
  const segments = path.split(/[\\/]/)
  for (let i = segments.length - 1; i >= 0; i--) {
    const date = parseUtcStamp(segments[i] ?? '')
    if (date) return date
  }
  return null
}

export interface UtcStampHint {
  /** Short local-time text, e.g. "Oct 7, 12:00 PM PDT". */
  label: string
  /** Full explanation for a tooltip. */
  title: string
}

export interface UtcStampFormatOptions {
  /** Override the viewer's locale (tests). */
  locale?: string
  /** Override the viewer's time zone (tests). */
  timeZone?: string
}

// `dateStyle`/`timeStyle` cannot be combined with `timeZoneName`, so the
// medium-date / short-time look is spelled out per component.
const SHORT: Intl.DateTimeFormatOptions = {
  month: 'short',
  day: 'numeric',
  hour: 'numeric',
  minute: '2-digit',
  timeZoneName: 'short',
}
const FULL: Intl.DateTimeFormatOptions = { ...SHORT, year: 'numeric' }

/** Describe a UTC moment in the viewer's locale and time zone. */
export function describeUtcStamp(date: Date, opts: UtcStampFormatOptions = {}): UtcStampHint {
  const fmt = (o: Intl.DateTimeFormatOptions, timeZone: string | undefined) =>
    new Intl.DateTimeFormat(opts.locale, { ...o, timeZone }).format(date)
  // The folder name already carries the year; the tooltip spells it out.
  const label = fmt(SHORT, opts.timeZone)
  const local = fmt(FULL, opts.timeZone)
  const utc = fmt(FULL, 'UTC')
  return { label, title: `Collected at ${local} in your time zone (${utc})` }
}

/** Hint for a name matching the UTC-stamp pattern exactly; null otherwise. */
export function utcStampHint(name: string, opts: UtcStampFormatOptions = {}): UtcStampHint | null {
  const date = parseUtcStamp(name)
  return date ? describeUtcStamp(date, opts) : null
}

/** Hint for a path containing a UTC-stamped segment; null otherwise. */
export function utcStampHintForPath(
  path: string,
  opts: UtcStampFormatOptions = {},
): UtcStampHint | null {
  const date = findUtcStampInPath(path)
  return date ? describeUtcStamp(date, opts) : null
}
