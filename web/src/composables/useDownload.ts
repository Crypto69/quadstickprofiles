// Handing bytes to the user as a file. Every export path ends here, so the one
// anchor trick lives in one place.
//
// In the desktop build the API has already written the file into the exports
// folder (the X-Export-Path header says where), and an <a download> on a blob:
// URL is unreliable inside a WebView, so there we reveal that file instead.
import { desktopApi } from '@/desktop'

/** How long the blob: URL is kept alive after the click; see `saveBlob`. */
const REVOKE_DELAY_MS = 1000

/**
 * Save a blob under `filename` through a transient download link, or, in the
 * desktop build with a known `exportPath`, reveal the file the server wrote.
 * Returns which of the two happened.
 */
export function saveBlob(
  blob: Blob,
  filename: string,
  exportPath?: string | null,
): 'downloaded' | 'revealed' {
  const desktop = desktopApi()
  if (desktop && exportPath) {
    void desktop.reveal(exportPath)
    return 'revealed'
  }
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  // Revoking straight after click() blanks or aborts the download in Safari and in
  // some Firefox versions: the browser has not finished reading the blob yet. A
  // second is far longer than any browser needs and costs only the blob's memory.
  setTimeout(() => URL.revokeObjectURL(url), REVOKE_DELAY_MS)
  return 'downloaded'
}
