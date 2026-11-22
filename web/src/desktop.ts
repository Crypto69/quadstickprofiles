// The desktop build (desktop/launcher.py) runs this app inside a pywebview window
// and exposes three native calls on window.pywebview.api. In a browser that object
// does not exist and every caller falls back to what it does today. Every call is
// a plain button on the web side: nothing to hold, nothing pointer-only.

export interface DesktopApi {
  /** Show an exported file in Finder / Explorer. Only paths inside the exports folder. */
  reveal(path: string): Promise<void>
  /** Open a URL of this app in the system browser (printing lives there). */
  open_external(url: string): Promise<void>
  /**
   * Ask for a folder (the QuadStick's drive) and return every file in it, base64.
   * `null` when the dialog is cancelled. A WebView's file input cannot pick a
   * folder, so the backup asks the shell instead. Optional so a test stub may omit it.
   */
  pick_drive_files?(): Promise<{ path: string; data: string }[] | null>
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
