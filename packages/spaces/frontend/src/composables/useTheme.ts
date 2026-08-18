import { ref, watch, onMounted } from 'vue'

export type Theme = 'light' | 'dark' | 'system'

const theme = ref<Theme>('system')
const isDark = ref(false)

interface TauriGlobal {
  core?: {
    invoke?: (command: string, args?: Record<string, unknown>) => Promise<unknown>
  }
}

// Function to detect system theme
function getSystemTheme(): 'light' | 'dark' {
  if (typeof window !== 'undefined') {
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
  }
  return 'light'
}

// Function to apply theme to document
function applyTheme(newTheme: 'light' | 'dark') {
  const root = document.documentElement

  if (newTheme === 'dark') {
    root.classList.add('dark')
    isDark.value = true
  } else {
    root.classList.remove('dark')
    isDark.value = false
  }
}

function syncNativeTheme(newTheme: 'light' | 'dark') {
  const tauri =
    typeof window !== 'undefined'
      ? (window as Window & { __TAURI__?: TauriGlobal }).__TAURI__
      : undefined
  if (!tauri?.core?.invoke) return

  tauri.core.invoke('update_theme', { isDark: newTheme === 'dark' }).catch(() => {
    // Native theme sync is best-effort for the browser/dev fallback.
  })
}

// Function to update theme
function updateTheme(newTheme: Theme) {
  theme.value = newTheme
  localStorage.setItem('theme', newTheme)

  let resolvedTheme: 'light' | 'dark'

  if (newTheme === 'system') {
    resolvedTheme = getSystemTheme()
  } else {
    resolvedTheme = newTheme
  }

  applyTheme(resolvedTheme)
  syncNativeTheme(resolvedTheme)
}

export function useTheme() {
  // Initialize theme on mount
  onMounted(() => {
    const stored = localStorage.getItem('theme') as Theme
    const initialTheme = stored || 'system'

    updateTheme(initialTheme)

    // Listen for system theme changes
    if (typeof window !== 'undefined') {
      const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')

      const handleChange = () => {
        if (theme.value === 'system') {
          const systemTheme = getSystemTheme()
          applyTheme(systemTheme)
          syncNativeTheme(systemTheme)
        }
      }

      mediaQuery.addEventListener('change', handleChange)

      // Cleanup
      return () => {
        mediaQuery.removeEventListener('change', handleChange)
      }
    }
  })

  // Watch for theme changes
  watch(theme, (newTheme) => {
    updateTheme(newTheme)
  })

  return {
    theme: readonly(theme),
    isDark: readonly(isDark),
    setTheme: updateTheme,
    toggleTheme: () => {
      const newTheme = isDark.value ? 'light' : 'dark'
      updateTheme(newTheme)
    },
  }
}

// Helper function to make reactive values readonly
function readonly<T>(ref: T) {
  return ref
}
