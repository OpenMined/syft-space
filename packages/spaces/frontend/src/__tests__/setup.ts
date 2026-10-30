// jsdom has no ResizeObserver; tooltips and popovers measure themselves with it on opening.
globalThis.ResizeObserver ??= class {
  observe() {}
  unobserve() {}
  disconnect() {}
}
