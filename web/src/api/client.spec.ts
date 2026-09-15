import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError, api } from './client'
import { catalog, conflict, fileResponse, stubFetch, unprocessable, validation } from '@/test/factories'

describe('api client', () => {
  beforeEach(() => {
    vi.unstubAllGlobals()
  })

  it('calls everything under /api', async () => {
    const fetchMock = stubFetch({ '/api/catalog': catalog() })
    vi.stubGlobal('fetch', fetchMock)
    await api.catalog()
    expect(fetchMock.mock.calls[0]![0]).toBe('/api/catalog')
  })

  it('turns a 409 into an error carrying the findings, so the UI can say why', async () => {
    const v = validation({
      errors: 1,
      findings: [{ severity: 'error', mode: 2, row: 9, message: 'Unknown output' }],
      consequence: { error: 'The QuadStick will not read this profile correctly.' },
    })
    vi.stubGlobal(
      'fetch',
      stubFetch({ '/api/profiles/1/export.csv': conflict('Export refused: fix the errors', v) }),
    )
    await expect(api.exportCsv(1)).rejects.toThrow(ApiError)
    try {
      await api.exportCsv(1)
    } catch (e) {
      const err = e as ApiError
      expect(err.isValidationBlock).toBe(true)
      expect(err.message).toContain('Export refused')
      expect(err.validation?.findings[0]?.message).toBe('Unknown output')
      expect(err.validation?.consequence.error).toContain('will not read')
    }
  })

  it('flattens a 422 field list into one readable message', async () => {
    vi.stubGlobal(
      'fetch',
      stubFetch({
        'POST /api/profiles': unprocessable([
          { loc: ['body', 'csv_filename'], msg: 'must end in .csv' },
          { loc: ['body', 'modes', 0, 'mappings', 0, 'output'], msg: "Unknown output 'nope'" },
        ]),
      }),
    )
    await expect(api.createProfile({ name: 'x', csv_filename: 'bad name.csv' })).rejects.toThrow(
      /csv_filename: must end in \.csv/,
    )
  })

  it('does not choke on a non-JSON error body from a proxy', async () => {
    vi.stubGlobal(
      'fetch',
      stubFetch({ '/api/catalog': { status: 502, body: '<html>502</html>' } }),
    )
    await expect(api.catalog()).rejects.toThrow(/502/)
  })

  it('omits empty query parameters instead of sending blanks', async () => {
    const fetchMock = stubFetch({
      '/api/profiles?validate=true': [],
      '/api/profiles': [],
    })
    vi.stubGlobal('fetch', fetchMock)
    await api.listProfiles({ q: '', validate: true })
    expect(fetchMock.mock.calls[0]![0]).toBe('/api/profiles?validate=true')
  })

  it('reads the filename and the export path from the response headers', async () => {
    vi.stubGlobal(
      'fetch',
      stubFetch({
        '/api/profiles/3/export.csv': fileResponse('a,b,\r\n', {
          filename: 'ddfortnite.csv',
          contentType: 'text/csv',
          exportPath: '/app/exports/ddfortnite.csv',
        }),
      }),
    )
    const dl = await api.exportCsv(3)
    expect(dl.filename).toBe('ddfortnite.csv')
    expect(dl.exportPath).toBe('/app/exports/ddfortnite.csv')
    expect(await dl.blob.text()).toBe('a,b,\r\n')
  })

  it('points the card at the API, not at the SPA router', () => {
    expect(api.cardUrl(7)).toBe('/api/profiles/7/card.html')
  })

  it('points the summary sheet at the API too', () => {
    expect(api.summaryUrl(7)).toBe('/api/profiles/7/summary.html')
  })
})
