import { globalIgnores } from 'eslint/config'
import { defineConfigWithVueTs, vueTsConfigs } from '@vue/eslint-config-typescript'
import pluginVue from 'eslint-plugin-vue'
import pluginOxlint from 'eslint-plugin-oxlint'
import skipFormatting from '@vue/eslint-config-prettier/skip-formatting'

export default defineConfigWithVueTs(
  {
    name: 'app/files-to-lint',
    files: ['**/*.{ts,mts,tsx,vue}'],
  },

  globalIgnores(['**/dist/**', '**/dist-ssr/**', '**/coverage/**']),

  pluginVue.configs['flat/essential'],
  vueTsConfigs.recommended,

  {
    name: 'app/ui-components',
    files: ['src/components/ui/**/*.vue'],
    rules: {
      'vue/multi-word-component-names': 'off',
    },
  },

  ...pluginOxlint.configs['flat/recommended'],
  skipFormatting,

  {
    // Layering guard: UI (components/pages) must not call the backend directly.
    // Go through the Pinia store — the single seam onto @/api. (ApiError and
    // wire types stay importable; only the endpoint modules are off-limits.)
    name: 'app/ui-no-direct-api',
    files: ['src/components/**/*.{ts,vue}', 'src/pages/**/*.{ts,vue}'],
    rules: {
      'no-restricted-imports': [
        'error',
        {
          patterns: [
            {
              group: ['@/api/endpoints', '@/api/endpoints/*'],
              message:
                'UI must not import API endpoints directly — route through the Pinia store (src/stores).',
            },
          ],
        },
      ],
    },
  },
)
