import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { healthOf, useProfilesStore } from './profiles'
import {
  conflict, deferredFetch, fileResponse, noContent, profile, stubFetch, summary, unprocessable,
  validation,
} from '@/test/factories'

describe('healthOf', () => {
  it('ranks errors over warnings, and says when nothing was checked', () => {
    expect(healthOf(validation({ errors: 2, warnings: 5 }))).toBe('errors')
    expect(healthOf(validation({ warnings: 1 }))).toBe('warnings')
    expect(healthOf(validation({ info: 9 }))).toBe('clean')
    expect(healthOf(null)).toBe('unknown')
  })
})

describe('profiles store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.unstubAllGlobals()
  })

  it('asks for validation counts so the library can show a badge', async () => {
    const fetchMock = stubFetch({ '/api/profiles?validate=true': [summary()] })
    vi.stubGlobal('fetch', fetchMock)
    const store = useProfilesStore()
    await store.load()
    expect(fetchMock.mock.calls[0]![0]).toContain('validate=true')
    expect(store.profiles).toHaveLength(1)
    expect(store.health(store.profiles[0]!)).toBe('clean')
  })

  it('passes the search term through', async () => {
    const fetchMock = stubFetch({ '/api/profiles?q=fort&validate=true': [summary()] })
    vi.stubGlobal('fetch', fetchMock)
    const store = useProfilesStore()
    store.search = 'fort'
    await store.load()
    expect(fetchMock.mock.calls[0]![0]).toContain('q=fort')
  })

  it('reports a failed load without throwing at the view', async () => {
    vi.stubGlobal('fetch', stubFetch({ '/api/profiles?validate=true': { status: 500, body: '{}' } }))
    const store = useProfilesStore()
    await store.load()
    expect(store.error).toBeTruthy()
    expect(store.loading).toBe(false)
    expect(store.profiles).toEqual([])
  })

  it('blocks an export with the findings, rather than surfacing a generic error', async () => {
    const v = validation({
      errors: 1,
      findings: [{ severity: 'error', mode: 2, row: 9, message: "Unknown output 'nope'" }],
      consequence: { error: 'The QuadStick will not read this profile correctly.' },
    })
    vi.stubGlobal(
      'fetch',
      stubFetch({
        '/api/profiles/1/export.csv': conflict('Export refused: fix the validation errors first', v),
        '/api/profiles?validate=true': [summary()],
      }),
    )
    const store = useProfilesStore()
    const dl = await store.exportFile(1, 'csv')
    expect(dl).toBeNull()
    expect(store.error).toBeNull() // not a generic failure
    expect(store.blocked?.profileId).toBe(1)
    expect(store.blocked?.message).toContain('Export refused')
    expect(store.blocked?.validation?.findings[0]?.row).toBe(9)
    store.dismissBlocked()
    expect(store.blocked).toBeNull()
  })

  it('returns the exported bytes and where the server put them', async () => {
    vi.stubGlobal(
      'fetch',
      stubFetch({
        '/api/profiles/1/export.csv': fileResponse('QuadStick Configuration,Version 1.4,,x\r\n', {
          filename: 'ddfortnite.csv',
          contentType: 'text/csv',
          exportPath: '/app/exports/ddfortnite.csv',
        }),
      }),
    )
    const store = useProfilesStore()
    const dl = await store.exportFile(1, 'csv')
    expect(dl?.filename).toBe('ddfortnite.csv')
    expect(dl?.exportPath).toBe('/app/exports/ddfortnite.csv')
    expect(await dl!.blob.text()).toContain('QuadStick Configuration')
    expect(store.busyId).toBeNull()
  })

  it('keeps the import findings so the dialog can show them, then reloads', async () => {
    const findings = validation({
      warnings: 1,
      findings: [{ severity: 'warning', mode: null, row: null, message: 'Reference Card is stale' }],
      consequence: { warning: 'The QuadStick still loads this profile…' },
    })
    const fetchMock = stubFetch({
      'POST /api/profiles/import': { profile: profile(), findings },
      '/api/profiles?validate=true': [summary()],
    })
    vi.stubGlobal('fetch', fetchMock)
    const store = useProfilesStore()
    const file = new File(['x'], 'ddfortnite.csv', { type: 'text/csv' })
    const result = await store.importFile(file)
    expect(result?.profile.name).toBe('ddfortnite')
    expect(store.lastImport?.findings.warnings).toBe(1)
    expect(store.profiles).toHaveLength(1) // the list refreshed
    store.dismissImport()
    expect(store.lastImport).toBeNull()
  })

  it('sends the import as multipart with the optional fields', async () => {
    const fetchMock = stubFetch({
      'POST /api/profiles/import': { profile: profile(), findings: validation() },
      '/api/profiles?validate=true': [],
    })
    vi.stubGlobal('fetch', fetchMock)
    const store = useProfilesStore()
    await store.importFile(new File(['x'], 'a.csv'), { game: 'Fortnite', firmware: 1476 })
    const body = fetchMock.mock.calls[0]![1]!.body as FormData
    expect(body.get('game')).toBe('Fortnite')
    expect(body.get('firmware')).toBe('1476')
    expect(body.get('file')).toBeInstanceOf(File)
  })

  it('duplicates, converts and deletes, refreshing the list each time', async () => {
    const fetchMock = stubFetch({
      'POST /api/profiles/1/duplicate': profile({ id: 2, csv_filename: 'ddfortnite_copy.csv' }),
      'POST /api/profiles/1/convert': {
        profile: profile({ id: 3, console: 'xbox' }),
        notes: [],
        suggested_csv_filename: 'ddfortnite_xbox.csv',
      },
      'DELETE /api/profiles/1': noContent(),
      '/api/profiles?validate=true': [summary()],
    })
    vi.stubGlobal('fetch', fetchMock)
    const store = useProfilesStore()

    const copy = await store.duplicate(1)
    expect(copy?.csv_filename).toBe('ddfortnite_copy.csv')

    const converted = await store.convert(1, 'xbox')
    expect(converted?.profile.console).toBe('xbox')
    const convertCall = fetchMock.mock.calls.find((c) => String(c[0]).includes('/convert'))!
    expect(JSON.parse(String(convertCall[1]!.body))).toEqual({ target: 'xbox' })

    expect(await store.remove(1)).toBe(true)
  })

  it('passes a chosen name and filename to duplicate', async () => {
    const fetchMock = stubFetch({
      'POST /api/profiles/1/duplicate?name=Tweak&csv_filename=tweak.csv': profile({ id: 2 }),
      '/api/profiles?validate=true': [],
    })
    vi.stubGlobal('fetch', fetchMock)
    const store = useProfilesStore()
    const copy = await store.duplicate(1, { name: 'Tweak', csv_filename: 'tweak.csv' })
    expect(copy).not.toBeNull()
  })

  it('passes a chosen name and filename to convert', async () => {
    const fetchMock = stubFetch({
      'POST /api/profiles/1/convert': {
        profile: profile({ id: 3, console: 'xbox', name: 'cvcodww2_xbox' }),
        notes: [],
        suggested_csv_filename: 'cvcodww2_xbox.csv',
      },
      '/api/profiles?validate=true': [],
    })
    vi.stubGlobal('fetch', fetchMock)
    const store = useProfilesStore()
    await store.convert(1, 'xbox', { name: 'cvcodww2_xbox', csv_filename: 'cvcodww2_xbox.csv' })
    const call = fetchMock.mock.calls.find((c) => String(c[0]).includes('/convert'))!
    expect(JSON.parse(String(call[1]!.body))).toEqual({
      target: 'xbox', name: 'cvcodww2_xbox', csv_filename: 'cvcodww2_xbox.csv',
    })
  })

  it('renames with PATCH, so the modes and preferences are never resent', async () => {
    // PATCH ignores modes and preferences by design (ProfilePatch), which is exactly
    // the guarantee wanted for a metadata-only edit: a stale library copy of the
    // document cannot clobber the profile's contents.
    const fetchMock = stubFetch({
      'PATCH /api/profiles/1': profile({ name: 'cvcodww2', csv_filename: 'cvcodww2.csv' }),
      '/api/profiles?validate=true': [summary({ name: 'cvcodww2', csv_filename: 'cvcodww2.csv' })],
    })
    vi.stubGlobal('fetch', fetchMock)
    const store = useProfilesStore()
    const p = await store.rename(1, { name: 'cvcodww2', csv_filename: 'cvcodww2.csv' })
    expect(p?.name).toBe('cvcodww2')
    const call = fetchMock.mock.calls.find((c) => c[1]?.method === 'PATCH')!
    expect(JSON.parse(String(call[1]!.body))).toEqual({
      name: 'cvcodww2', csv_filename: 'cvcodww2.csv',
    })
    // and the list reflects it
    expect(store.profiles[0]!.csv_filename).toBe('cvcodww2.csv')
    expect(store.error).toBeNull()
  })

  it('reports a rejected rename without leaving the list changed', async () => {
    vi.stubGlobal(
      'fetch',
      stubFetch({
        'PATCH /api/profiles/1': unprocessable([
          { loc: ['body', 'csv_filename'], msg: 'must end in .csv' },
        ]),
      }),
    )
    const store = useProfilesStore()
    expect(await store.rename(1, { name: 'x', csv_filename: 'bad name' })).toBeNull()
    expect(store.error).toContain('must end in .csv')
    expect(store.busyId).toBeNull()
  })

  it('reports a bad new-profile filename instead of silently doing nothing', async () => {
    vi.stubGlobal(
      'fetch',
      stubFetch({
        'POST /api/profiles': unprocessable([
          { loc: ['body', 'csv_filename'], msg: 'must end in .csv' },
        ]),
      }),
    )
    const store = useProfilesStore()
    const p = await store.create({ name: 'x', csv_filename: 'bad name.csv' })
    expect(p).toBeNull()
    expect(store.error).toContain('must end in .csv')
  })

  it('a slower earlier search cannot overwrite a newer one', async () => {
    // Typing in the search box leaves two requests in flight; the one that answers
    // last would otherwise decide the list, however stale its query.
    const { fetch, calls } = deferredFetch()
    vi.stubGlobal('fetch', fetch)
    const store = useProfilesStore()

    const older = store.load({ q: 'fo' })
    const newer = store.load({ q: 'fort' })
    expect(calls).toHaveLength(2)

    calls[1]!.release([summary({ id: 2, name: 'fortnite' })])
    await newer
    expect(store.profiles.map((p) => p.name)).toEqual(['fortnite'])
    expect(store.loading).toBe(false)

    calls[0]!.release([summary({ id: 3, name: 'forza' }), summary({ id: 4, name: 'fortnite' })])
    await older
    expect(store.profiles.map((p) => p.name)).toEqual(['fortnite'])
    expect(store.loading).toBe(false)
  })

  it('a late failure from an older search does not raise the banner', async () => {
    const { fetch, calls } = deferredFetch()
    vi.stubGlobal('fetch', fetch)
    const store = useProfilesStore()

    const older = store.load({ q: 'fo' })
    const newer = store.load({ q: 'fort' })
    calls[1]!.release([summary()])
    await newer
    calls[0]!.release({ detail: 'boom' }, 500)
    await older
    expect(store.error).toBeNull()
    expect(store.profiles).toHaveLength(1)
  })

  it('knows which profiles may be exported', () => {
    const store = useProfilesStore()
    expect(store.canExport(summary({ validation: validation() }))).toBe(true)
    expect(store.canExport(summary({ validation: validation({ warnings: 3 }) }))).toBe(true)
    expect(store.canExport(summary({ validation: validation({ errors: 1 }) }))).toBe(false)
  })
})
