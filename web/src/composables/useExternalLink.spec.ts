import { afterEach, describe, expect, it, vi } from 'vitest'
import { openExternal } from './useExternalLink'

describe('openExternal', () => {
  afterEach(() => {
    delete window.pywebview
  })

  it('opens a new tab in a browser', () => {
    const openSpy = vi.fn()
    vi.stubGlobal('open', openSpy)
    expect(openExternal('/api/profiles/1/card.html')).toBe('tab')
    expect(openSpy).toHaveBeenCalledWith('/api/profiles/1/card.html', '_blank', 'noopener')
  })

  it('hands an absolute URL to the system browser in the desktop build', () => {
    const openSpy = vi.fn()
    vi.stubGlobal('open', openSpy)
    const open_external = vi.fn().mockResolvedValue(undefined)
    window.pywebview = { api: { reveal: vi.fn(), open_external } }
    expect(openExternal('/api/profiles/1/card.html')).toBe('browser')
    expect(open_external).toHaveBeenCalledWith(
      `${window.location.origin}/api/profiles/1/card.html`,
    )
    expect(openSpy).not.toHaveBeenCalled()
  })
})
