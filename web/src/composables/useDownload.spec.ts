import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { saveBlob } from './useDownload'

function trapAnchors() {
  const anchors: HTMLAnchorElement[] = []
  const orig = document.createElement.bind(document)
  vi.spyOn(document, 'createElement').mockImplementation((tag: string) => {
    const el = orig(tag) as HTMLElement
    if (tag === 'a') {
      el.click = vi.fn()
      anchors.push(el as HTMLAnchorElement)
    }
    return el
  })
  return anchors
}

describe('saveBlob', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
    delete window.pywebview
  })

  it('clicks a download link for the blob and releases the object URL later', () => {
    const anchors = trapAnchors()
    const create = vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:one')
    const revoke = vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {})

    const blob = new Blob(['x'], { type: 'text/csv' })
    expect(saveBlob(blob, 'ddfortnite.csv')).toBe('downloaded')

    expect(create).toHaveBeenCalledWith(blob)
    expect(anchors).toHaveLength(1)
    expect(anchors[0]!.getAttribute('href')).toBe('blob:one')
    expect(anchors[0]!.download).toBe('ddfortnite.csv')
    expect(anchors[0]!.click).toHaveBeenCalledTimes(1)
    // Revoking in the same tick as the click blanks the download in Safari and in
    // some Firefox versions: the browser has not read the blob yet.
    expect(revoke).not.toHaveBeenCalled()

    vi.runAllTimers()
    expect(revoke).toHaveBeenCalledTimes(1)
    expect(revoke).toHaveBeenCalledWith('blob:one')
  })

  it('reveals the file the server wrote in the desktop build', () => {
    const anchors = trapAnchors()
    const reveal = vi.fn().mockResolvedValue(undefined)
    window.pywebview = { api: { reveal, open_external: vi.fn() } }

    const blob = new Blob(['x'], { type: 'text/csv' })
    expect(saveBlob(blob, 'ddfortnite.csv', '/Users/me/Documents/QuadStick exports/ddfortnite.csv')).toBe('revealed')

    expect(reveal).toHaveBeenCalledWith('/Users/me/Documents/QuadStick exports/ddfortnite.csv')
    expect(anchors).toHaveLength(0)
  })

  it('still downloads in the desktop build when the server gave no path', () => {
    const anchors = trapAnchors()
    vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:two')
    vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {})
    window.pywebview = { api: { reveal: vi.fn(), open_external: vi.fn() } }

    expect(saveBlob(new Blob(['x']), 'prefs.csv', null)).toBe('downloaded')
    expect(anchors).toHaveLength(1)
  })
})
