/** Google Identity Services: load the script once, render the sign-in button. */

interface GoogleIdApi {
  accounts: {
    id: {
      initialize(config: {
        client_id: string
        callback: (response: { credential: string }) => void
      }): void
      renderButton(el: HTMLElement, options: Record<string, unknown>): void
    }
  }
}

declare global {
  interface Window {
    google?: GoogleIdApi
  }
}

const GIS_SRC = 'https://accounts.google.com/gsi/client'

let scriptPromise: Promise<void> | null = null

function loadScript(): Promise<void> {
  scriptPromise ??= new Promise((resolve, reject) => {
    const script = document.createElement('script')
    script.src = GIS_SRC
    script.async = true
    script.onload = () => resolve()
    script.onerror = () => reject(new Error('Failed to load Google Sign-In'))
    document.head.appendChild(script)
  })
  return scriptPromise
}

/** Render the Google button into `target`; `onCredential` gets the ID token. */
export async function renderGoogleButton(
  target: HTMLElement,
  clientId: string,
  onCredential: (credential: string) => void,
): Promise<void> {
  await loadScript()
  const google = window.google
  if (!google) throw new Error('Google Sign-In unavailable')
  google.accounts.id.initialize({
    client_id: clientId,
    callback: (response) => onCredential(response.credential),
  })
  google.accounts.id.renderButton(target, {
    theme: 'outline',
    size: 'large',
    text: 'continue_with',
    width: 320,
  })
}
