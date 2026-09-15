// Opening one of the API's printable pages (card, summary) outside this app's
// layout. In a browser that is a new tab; in the desktop build a WebView cannot
// open tabs and has no print dialog, so the system browser gets the URL instead.
import { desktopApi } from '@/desktop'

/** Open `url` (relative to this origin) in a new tab or the system browser. */
export function openExternal(url: string): 'tab' | 'browser' {
  const desktop = desktopApi()
  if (desktop) {
    void desktop.open_external(new URL(url, window.location.origin).href)
    return 'browser'
  }
  window.open(url, '_blank', 'noopener')
  return 'tab'
}
