import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { healthOf, useProfilesStore } from './profiles'
import {
  conflict, fileResponse, noContent, profile, stubFetch, summary, unprocessable, validation,
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

  it('knows which profiles may be exported', () => {
    const store = useProfilesStore()
    expect(store.canExport(summary({ validation: validation() }))).toBe(true)
    expect(store.canExport(summary({ validation: validation({ warnings: 3 }) }))).toBe(true)
    expect(store.canExport(summary({ validation: validation({ errors: 1 }) }))).toBe(false)
  })
})
