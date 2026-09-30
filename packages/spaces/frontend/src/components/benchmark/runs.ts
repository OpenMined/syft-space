/**
 * Shapes the run cards pass between themselves.
 *
 * In a plain module rather than in one of the components: `<script setup>` is
 * not an ES module anyone can export from, and a type that two components
 * share has to live where both can import it.
 */

/** Where a published card can be seen, already resolved to a link. */
export interface RunMarketplace {
  id: string
  name: string
  /** The endpoint's own page at that marketplace. */
  url: string
}
