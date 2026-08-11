import { onMounted, ref } from 'vue'

export type Theme = 'light' | 'dark' | 'system'

const theme = ref<Theme>('system')
const isDark = ref(false)
let initialized = false

function getSystemTheme(): 'light' | 'dark' {
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

function applyTheme(resolved: 'light' | 'dark') {
  document.documentElement.classList.toggle('dark', resolved === 'dark')
  isDark.value = resolved === 'dark'
}

function setTheme(next: Theme) {
  theme.value = next
  localStorage.setItem('theme', next)
  applyTheme(next === 'system' ? getSystemTheme() : next)
}

export function useTheme() {
  onMounted(() => {
    if (initialized) return
    initialized = true
    const stored = localStorage.getItem('theme') as Theme | null
    setTheme(stored ?? 'system')
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
      if (theme.value === 'system') applyTheme(getSystemTheme())
    })
  })

  return { theme, isDark, setTheme }
}
