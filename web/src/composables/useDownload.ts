// Handing bytes to the user as a file. Every export path ends here, so the one
// anchor trick lives in one place.
//
// In the desktop build the API has already written the file into the exports
// folder (the X-Export-Path header says where), and an <a download> on a blob:
// URL is unreliable inside a WebView, so there we reveal that file instead.
import { desktopApi } from '@/desktop'

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
  URL.revokeObjectURL(url)
  return 'downloaded'
}
