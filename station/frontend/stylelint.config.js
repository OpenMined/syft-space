/**
 * OMDS enforcement gate — makes raw color values un-shippable: every color must
 * be a design token (var(--…)). Three focused rules; deliberately minimal (no
 * stylelint-config-standard) so it stays high-signal for humans and agents.
 *
 * ignoreFiles exempts the two files that legitimately hold literal values:
 * the vendored OMDS palette, and src/style.css (this app's token/adapter layer,
 * where the shadow scale carries literal hex).
 */

// `/color$/` matches color, background-color, border-*-color, outline-color,
// caret-color, text-decoration-color — but NOT color-scheme. box-shadow is
// excluded (the ring hack tokenizes color but isn't a single var()); color-no-hex
// + color-named still police shadow colors.
const COLOR_PROPS = ['/color$/', 'fill', 'stroke']
const ALLOWED_KEYWORDS = [
  'currentColor',
  'transparent',
  'inherit',
  'initial',
  'unset',
  'revert',
  'none',
]

export default {
  ignoreFiles: [
    'dist/**',
    'node_modules/**',
    // Raw hex is correct only in the token-definition layer.
    'src/brand/**',
    'src/style.css',
  ],

  // Lint <style> blocks inside .vue SFCs.
  overrides: [{ files: ['**/*.vue'], customSyntax: 'postcss-html' }],

  plugins: ['stylelint-declaration-strict-value'],

  rules: {
    'color-no-hex': [
      true,
      {
        message:
          'OMDS: no raw hex. Use a token — e.g. var(--color-teal-600), var(--surface-background-default), var(--text-body).',
      },
    ],
    'color-named': [
      'never',
      {
        message: 'OMDS: no named colors. Use a design token via var(--…).',
      },
    ],
    'scale-unlimited/declaration-strict-value': [
      COLOR_PROPS,
      {
        ignoreKeywords: ALLOWED_KEYWORDS,
        ignoreFunctions: false, // disallow rgb()/hsl() literals — only var() passes
        disableFix: true,
        message:
          'OMDS: color properties must reference a design token — use var(--…), not a literal value.',
      },
    ],
  },
}
