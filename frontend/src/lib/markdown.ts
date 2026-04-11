export const markdownToHtml = (markdown: string): string => {
  if (!markdown) return ''

  const inline = markdown
    .replace(/^### (.*$)/gim, '<h3>$1</h3>')
    .replace(/^## (.*$)/gim, '<h2>$1</h2>')
    .replace(/^# (.*$)/gim, '<h1>$1</h1>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/\*([^*]+)\*/g, '<em>$1</em>')
    .replace(/```(\w+)?\n([^`]+)```/g, '<pre><code>$2</code></pre>')
    .replace(/```([^`]+)```/g, '<pre><code>$1</code></pre>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(
      /\[([^\]]+)\]\(([^)]+)\)/g,
      '<a href="$2" class="text-primary hover:text-primary/80 underline">$1</a>',
    )
    .replace(/\n\n/g, '</p><p>')

  const OL_CLASS = 'list-decimal list-inside space-y-1'
  const UL_CLASS = 'list-disc list-inside space-y-1'

  const out: string[] = []
  let listType: 'ol' | 'ul' | null = null
  const closeList = () => {
    if (listType) {
      out.push(`</${listType}>`)
      listType = null
    }
  }

  for (const line of inline.split('\n')) {
    const ordered = /^\d+\.\s(.*)$/.exec(line)
    const unordered = /^-\s(.*)$/.exec(line)
    if (ordered) {
      if (listType !== 'ol') {
        closeList()
        out.push(`<ol class="${OL_CLASS}">`)
        listType = 'ol'
      }
      out.push(`<li>${ordered[1]}</li>`)
    } else if (unordered) {
      if (listType !== 'ul') {
        closeList()
        out.push(`<ul class="${UL_CLASS}">`)
        listType = 'ul'
      }
      out.push(`<li>${unordered[1]}</li>`)
    } else {
      closeList()
      out.push(line)
    }
  }
  closeList()

  return ('<p>' + out.join('\n') + '</p>').replace(/<p>\s*<\/p>/g, '')
}

export const stripMarkdown = (markdown: string): string => {
  if (!markdown) return ''

  return markdown.replace(/[#*`]/g, '').replace(/^• /gm, '').replace(/^- /gm, '').trim()
}
