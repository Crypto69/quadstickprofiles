// The desktop build (desktop/launcher.py) runs this app inside a pywebview window
// and exposes a few native calls on window.pywebview.api. In a browser that object
// does not exist and every caller falls back to what it does today. Every call is
// a plain button on the web side: nothing to hold, nothing pointer-only.

export interface DesktopApi {
  /** Show an exported file in Finder / Explorer. Only paths inside the exports folder. */
  reveal(path: string): Promise<void>
  /** Open a URL of this app in the system browser (printing lives there). */
  open_external(url: string): Promise<void>
  // The QuadStick's drive. A web page cannot see what is plugged in; the desktop app
  // can, so it finds the drive by name and remembers it (desktop/desktop_api.py).
  // Optional so a test stub may omit them.
  /** What is on the drive now: names and sizes. */
  quadstick_drive?(): Promise<DriveState>
  /** Every file on the drive, base64, for a backup. `null` when it is not plugged in. */
  read_quadstick_drive?(): Promise<{ path: string; data: string }[] | null>
  /** Ask which drive is the QuadStick and remember its name. `null` when cancelled. */
  choose_quadstick_drive?(): Promise<DriveState | null>
  /**
   * Put these profiles (`data` base64) on the drive in place of the ones there now,
   * and flush. Answers with what is on the drive after. Rejects with a message when
   * it refuses or the drive is not plugged in. The only call that writes to the drive.
   */
  write_quadstick_drive?(files: { name: string; data: string }[]): Promise<DriveState>
}

export interface DriveState {
  /** Plugged in and found. */
  found: boolean
  /** The drive's name; not found, the name being looked for. */
  name: string
  files: { path: string; size: number }[]
  /**
   * Mac App Store build only: the drive is plugged in, but Apple's sandbox lets the app
   * open it only after it has been picked once in the folder dialog.
   */
  needs_permission?: boolean
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
