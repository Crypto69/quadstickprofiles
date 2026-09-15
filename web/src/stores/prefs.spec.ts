import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { usePrefsStore } from './prefs'
import { fileResponse, prefs, stubFetch, validation } from '@/test/factories'

describe('prefs store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.unstubAllGlobals()
  })

  it('loads the device settings and starts clean', async () => {
    vi.stubGlobal('fetch', stubFetch({ '/api/prefs': prefs({ volume: '40' }) }))
    const store = usePrefsStore()
    await store.load()
    expect(store.values).toEqual({ volume: '40' })
    expect(store.dirty).toBe(false)
  })

  it('removes a key when it is blanked, rather than storing an empty string', async () => {
    vi.stubGlobal('fetch', stubFetch({ '/api/prefs': prefs({ volume: '40' }) }))
    const store = usePrefsStore()
    await store.load()
    store.set('volume', '')
    expect('volume' in store.values).toBe(false)
    expect(store.dirty).toBe(true)
  })

  it('saves and becomes clean again', async () => {
    vi.stubGlobal(
      'fetch',
      stubFetch({
        '/api/prefs': prefs({ volume: '40' }),
        'PUT /api/prefs': prefs({ volume: '10' }),
      }),
    )
    const store = usePrefsStore()
    await store.load()
    store.set('volume', '10')
    expect(await store.save()).toBe(true)
    expect(store.values).toEqual({ volume: '10' })
    expect(store.dirty).toBe(false)
  })

  it('keeps a refused edit on screen with the reason', async () => {
    const refusal = validation({
      errors: 1,
      findings: [
        { severity: 'error', mode: null, row: null, message: 'Speaker volume (volume) is 900; the highest the QuadStick accepts is 100' },
      ],
    })
    vi.stubGlobal(
      'fetch',
      stubFetch({
        '/api/prefs': prefs({ volume: '40' }),
        'PUT /api/prefs': {
          status: 422,
          body: JSON.stringify({
            detail: { message: 'Some settings are outside what the QuadStick accepts', validation: refusal },
          }),
          headers: { 'Content-Type': 'application/json' },
        },
      }),
    )
    const store = usePrefsStore()
    await store.load()
    store.set('volume', '900')
    expect(await store.save()).toBe(false)
    expect(store.values.volume).toBe('900') // still there to fix
    expect(store.dirty).toBe(true)
    expect(store.refused?.findings[0]?.message).toContain('the highest the QuadStick accepts')
  })

  it('reverts to the last saved set', async () => {
    vi.stubGlobal('fetch', stubFetch({ '/api/prefs': prefs({ volume: '40' }) }))
    const store = usePrefsStore()
    await store.load()
    store.set('volume', '99')
    store.set('mouse_speed', '150')
    store.revert()
    expect(store.values).toEqual({ volume: '40' })
    expect(store.dirty).toBe(false)
  })

  it('imports a prefs.csv, replacing what was there', async () => {
    vi.stubGlobal(
      'fetch',
      stubFetch({
        '/api/prefs': prefs({ volume: '40' }),
        'POST /api/prefs/import': prefs({ brightness: '9' }),
      }),
    )
    const store = usePrefsStore()
    await store.load()
    const r = await store.importFile(new File(['x'], 'prefs.csv'))
    expect(r?.preferences).toEqual({ brightness: '9' })
    expect(store.values).toEqual({ brightness: '9' })
    expect(store.dirty).toBe(false) // what came back is now the saved state
  })

  it('exports the file with the name the device expects', async () => {
    vi.stubGlobal(
      'fetch',
      stubFetch({
        '/api/prefs': prefs({ volume: '40' }),
        '/api/prefs/export.csv': fileResponse('Preferences,\r\n', {
          filename: 'prefs.csv',
          contentType: 'text/csv',
          exportPath: '/app/exports/prefs.csv',
        }),
      }),
    )
    const store = usePrefsStore()
    await store.load()
    const dl = await store.exportFile()
    expect(dl?.filename).toBe('prefs.csv')
    expect(dl?.exportPath).toBe('/app/exports/prefs.csv')
  })

  it('sends the firmware it was given on every call, and none when it has none', async () => {
    const fetchMock = stubFetch({
      '/api/prefs': prefs({ volume: '40' }),
      '/api/prefs?firmware=1476': prefs({ volume: '40' }),
      'PUT /api/prefs?firmware=1476': prefs({ volume: '10' }),
      'POST /api/prefs/import?firmware=1476': prefs({ brightness: '9' }),
      '/api/prefs/export.csv?firmware=1476': fileResponse('Preferences,\r\n', {
        filename: 'prefs.csv', contentType: 'text/csv',
      }),
    })
    vi.stubGlobal('fetch', fetchMock)
    const store = usePrefsStore()
    await store.load() // no firmware yet: the API's default applies
    expect(fetchMock.mock.calls.at(-1)?.[0]).toBe('/api/prefs')

    store.firmware = 1476
    await store.load()
    store.set('volume', '10')
    expect(await store.save()).toBe(true)
    expect(await store.importFile(new File(['x'], 'prefs.csv'))).not.toBeNull()
    expect((await store.exportFile())?.filename).toBe('prefs.csv')
    const urls = fetchMock.mock.calls.slice(1).map((c) => String(c[0]))
    expect(urls).toEqual([
      '/api/prefs?firmware=1476',
      '/api/prefs?firmware=1476',
      '/api/prefs/import?firmware=1476',
      '/api/prefs/export.csv?firmware=1476',
    ])
  })

  it('will not export an empty set or one with errors', async () => {
    vi.stubGlobal('fetch', stubFetch({ '/api/prefs': prefs({}) }))
    const store = usePrefsStore()
    await store.load()
    expect(store.canExport).toBe(false) // nothing to write

    store.set('volume', '40')
    store.validation = validation({ errors: 1 })
    expect(store.canExport).toBe(false) // the device would not read it
    store.validation = validation({ warnings: 2 })
    expect(store.canExport).toBe(true) // warnings still export
  })
})
