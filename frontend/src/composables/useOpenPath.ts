export function useOpenPath() {
  const openPath = async (path: string) => {
    if (typeof window !== 'undefined' && window.__TAURI__) {
      try {
        await window.__TAURI__.shell.open(path)
      } catch (error) {
        console.error('Failed to open path:', error)
      }
    }
  }

  return { openPath }
}
