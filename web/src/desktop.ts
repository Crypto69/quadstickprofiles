// The desktop build (desktop/launcher.py) runs this app inside a pywebview window
// and exposes two native calls on window.pywebview.api. In a browser that object
// does not exist and every caller falls back to what it does today. Both calls are
// plain buttons on the web side: nothing to hold, nothing pointer-only.

export interface DesktopApi {
  /** Show an exported file in Finder / Explorer. Only paths inside the exports folder. */
  reveal(path: string): Promise<void>
  /** Open a URL of this app in the system browser (printing lives there). */
  open_external(url: string): Promise<void>
}

declare global {
  interface Window {
    pywebview?: { api: DesktopApi }
  }
}

export function desktopApi(): DesktopApi | null {
  if (typeof window === 'undefined') return null
  return window.pywebview?.api ?? null
}

export function isDesktop(): boolean {
  return desktopApi() !== null
}
