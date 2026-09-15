import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useCatalogStore } from './catalog'
import { catalog, stubFetch } from '@/test/factories'

describe('catalog store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.unstubAllGlobals()
  })

  it('fetches once, and concurrent callers share the request', async () => {
    const fetchMock = stubFetch({ '/api/catalog': catalog() })
    vi.stubGlobal('fetch', fetchMock)
    const store = useCatalogStore()
    await Promise.all([store.load(), store.load(), store.load()])
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(store.loaded).toBe(true)
    await store.load()
    expect(fetchMock).toHaveBeenCalledTimes(1) // cached
  })

  it('records the error and lets the caller retry', async () => {
    vi.stubGlobal('fetch', stubFetch({ '/api/catalog': { status: 503, body: '{}' } }))
    const store = useCatalogStore()
    await expect(store.load()).rejects.toThrow()
    expect(store.error).toBeTruthy()
    expect(store.loaded).toBe(false)

    vi.stubGlobal('fetch', stubFetch({ '/api/catalog': catalog() }))
    await store.load(true)
    expect(store.loaded).toBe(true)
    expect(store.error).toBeNull()
  })

  it('does not offer the older input names, but still recognises them', async () => {
    vi.stubGlobal('fetch', stubFetch({ '/api/catalog': catalog() }))
    const store = useCatalogStore()
    await store.load()
    expect(store.currentInputs.map((i) => i.name)).not.toContain('push')
    expect(store.currentInputs.map((i) => i.name)).toContain('lip')
    expect(store.isLegacyInput('push')).toBe(true)
    expect(store.isLegacyInput('lip')).toBe(false)
    // a legacy name still resolves to a label, so an imported profile reads sensibly
    expect(store.inputLabel('push')).toContain('older name')
  })

  it('shows the naming set the profile uses', async () => {
    vi.stubGlobal('fetch', stubFetch({ '/api/catalog': catalog() }))
    const store = useCatalogStore()
    await store.load()
    expect(store.outputLabel('x', 'playstation')).toBe('x')
    expect(store.outputLabel('x', 'xbox')).toBe('A')
    expect(store.outputGlyph('x', 'playstation')).toBe('✕')
    expect(store.outputGlyph('x', 'xbox')).toBe('A')
    // increment_mode has no Xbox rename: it must not disappear
    expect(store.outputLabel('increment_mode', 'xbox')).toBe('increment_mode')
    expect(store.outputDescription('increment_mode')).toBe('Next mode')
  })

  it('groups outputs for a picker in one shape, under the naming set asked for', async () => {
    vi.stubGlobal('fetch', stubFetch({ '/api/catalog': catalog() }))
    const store = useCatalogStore()
    await store.load()
    const ps = store.outputGroups('playstation')
    expect(ps.map((g) => g.grp)).toEqual(['button', 'stick', 'system'])
    expect(ps[0]!.items[0]).toEqual({ name: 'x', shown: 'x', label: 'Cross' })
    // the stored name never changes with the console; only what is shown does
    const xbox = store.outputGroups('xbox')
    expect(xbox[0]!.items[0]).toEqual({ name: 'x', shown: 'A', label: 'Cross' })
    // no Xbox rename: shown stays the keyword, and the label still reads sensibly
    expect(xbox[2]!.items.find((o) => o.name === 'increment_mode')).toEqual({
      name: 'increment_mode', shown: 'increment_mode', label: 'Next mode',
    })
    // the default naming set is PlayStation
    expect(store.outputGroups()).toEqual(ps)
  })

  it('offers no outputs before the catalog has loaded', () => {
    const store = useCatalogStore()
    expect(store.outputGroups()).toEqual([])
  })

  it('answers the drive-hiding question per firmware, not per mode number', async () => {
    vi.stubGlobal('fetch', stubFetch({ '/api/catalog': catalog() }))
    const store = useCatalogStore()
    await store.load()
    // 2373 hides on 5/6/7
    expect(store.hidesFlashDrive(6, 2373)).toBe(true)
    expect(store.hidesFlashDrive(4, 2373)).toBe(false)
    expect(store.hidesFlashDrive(3, 2373)).toBe(false)
    // the older 1476 hid on 3/5/7
    expect(store.hidesFlashDrive(3, 1476)).toBe(true)
    expect(store.hidesFlashDrive(6, 1476)).toBe(false)
    // unset emulation mode is not a warning
    expect(store.hidesFlashDrive(null, 2373)).toBe(false)
    // an unknown firmware is "cannot tell" — neither "hides" nor "safe"
    expect(store.hidesFlashDrive(6, 9999)).toBeNull()
    expect(store.hidesFlashDrive(4, 9999)).toBeNull()
    // ...unless no emulation mode is set, when there is nothing to hide with
    expect(store.hidesFlashDrive(null, 9999)).toBe(false)
  })

  it('falls back to the keyword when the catalog has not loaded', () => {
    const store = useCatalogStore()
    expect(store.outputLabel('x')).toBe('x')
    expect(store.inputLabel('lip')).toBe('lip')
    expect(store.hidesFlashDrive(6, 2373)).toBe(false)
  })
})
