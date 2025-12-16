/**
 * Markdown processing utilities
 */

export const markdownToHtml = (markdown: string): string => {
  if (!markdown) return ''

  let html = markdown
    // Headers
    .replace(/^### (.*$)/gim, '<h3 class="text-lg font-semibold text-gray-900 mb-2 mt-4">$1</h3>')
    .replace(/^## (.*$)/gim, '<h2 class="text-xl font-semibold text-gray-900 mb-3 mt-5">$1</h2>')
    .replace(/^# (.*$)/gim, '<h1 class="text-2xl font-bold text-gray-900 mb-4 mt-6">$1</h1>')

    // Bold and italic
    .replace(/\*\*(.*?)\*\*/g, '<strong class="font-semibold text-gray-900">$1</strong>')
    .replace(/\*(.*?)\*/g, '<em class="italic text-gray-700">$1</em>')

    // Code blocks and inline code
    .replace(
      /`([^`]+)`/g,
      '<code class="bg-gray-100 text-gray-800 px-1 py-0.5 rounded text-sm font-mono">$1</code>',
    )

    // Lists
    .replace(/^• (.*$)/gim, '<li class="text-gray-700 mb-1">$1</li>')
    .replace(/^- (.*$)/gim, '<li class="text-gray-700 mb-1">$1</li>')

    // Line breaks
    .replace(/\n\n/g, '</p><p class="text-gray-700 mb-3">')
    .replace(/\n/g, '<br>')

  // Wrap in paragraph tags if not already wrapped
  if (
    !html.includes('<p>') &&
    !html.includes('<h1>') &&
    !html.includes('<h2>') &&
    !html.includes('<h3>')
  ) {
    html = `<p class="text-gray-700 mb-3">${html}</p>`
  } else if (html.includes('<li>')) {
    // Wrap lists in ul tags
    html = html.replace(/(<li.*?<\/li>)/g, (match) => {
      return `<ul class="list-disc list-inside mb-4 space-y-1">${match}</ul>`
    })
  }

  return html
}

export const stripMarkdown = (markdown: string): string => {
  if (!markdown) return ''

  return markdown.replace(/[#*`]/g, '').replace(/^• /gm, '').replace(/^- /gm, '').trim()
}
