/**
 * User-facing copy for each data source type, keyed by the backend's dtype.
 *
 * The backend schema supplies structure — which fields exist, which are
 * required, their type and format — and is the fallback for labels and
 * descriptions when an entry here is missing. This module only names things
 * for humans, so the source picker and any page that reports a chosen source
 * read the same labels instead of hard-coding their own.
 */

export interface FieldCopy {
  label?: string
  placeholder?: string
  // Render as a chip list. Values are joined with `separator` into the
  // single string the backend config field expects.
  list?: { separator: string }
}

export interface SourceCopy {
  label: string
  icon: string
  description?: string
  fields?: Record<string, FieldCopy>
}

// Presentation layer: all user-facing copy lives here, keyed by source type.
// The backend schema supplies structure (which fields, required, type/format)
// and is the fallback for labels/description when an entry is missing here.
export const SOURCE_PRESENTATION: Record<string, SourceCopy> = {
  local_file: {
    label: 'Local files',
    icon: '📁',
    description: 'Files and folders from this machine.',
  },
  wordpress: {
    label: 'WordPress',
    icon: '📰',
    description: 'Posts and pages from a self-hosted WordPress site.',
    fields: {
      siteUrl: { label: 'Site URL', placeholder: 'https://example.com' },
      username: { label: 'Username', placeholder: 'wp-admin user_login' },
      applicationPassword: {
        label: 'Application password',
        placeholder: 'Generate under Users → Profile → Application Passwords',
      },
    },
  },
  blogspot: {
    label: 'Blogspot',
    icon: '✍️',
    description: 'Posts from public Blogger blogs. One API key covers any number of blogs.',
    fields: {
      blogUrls: {
        label: 'Blog URLs',
        placeholder: 'https://example.blogspot.com',
        list: { separator: ',' },
      },
      apiKey: {
        label: 'API key',
        placeholder: 'Google API key with the Blogger API enabled',
      },
    },
  },
  rss: {
    label: 'RSS / Atom',
    icon: '📡',
    description:
      'Items from public RSS or Atom feeds. No credentials — a feed only shows its most recent items.',
    fields: {
      feedUrls: {
        label: 'Feed URLs',
        placeholder: 'https://example.com/feed',
        list: { separator: ',' },
      },
    },
  },
}

export const sourcePresentation = (name: string): SourceCopy =>
  SOURCE_PRESENTATION[name] ?? { label: name, icon: '🗂️' }
