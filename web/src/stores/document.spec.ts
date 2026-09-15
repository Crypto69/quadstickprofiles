import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fromProfile, toBody, useDocumentStore } from './document'
import { budget, editableProfile, stubFetch, validation } from '@/test/factories'

function routes(extra: Record<string, unknown> = {}) {
  return {
    '/api/profiles/1': editableProfile(),
    'POST /api/profiles/validate': validation({ budget: budget() }),
    ...extra,
  }
}

async function loaded(extra: Record<string, unknown> = {}) {
  vi.stubGlobal('fetch', stubFetch(routes(extra)))
  const store = useDocumentStore()
  await store.load(1)
  return store
}

/**
 * A fetch whose answers the test releases itself, in any order — for the race
 * tests, where what matters is which response lands last, not which was sent last.
 */
function deferredFetch() {
  const calls: { key: string; release: (body: unknown, status?: number) => void }[] = []
  const fetch = vi.fn(
    (input: RequestInfo | URL, init?: RequestInit) =>
      new Promise<Response>((resolve) => {
        const url = typeof input === 'string' ? input : input.toString()
        calls.push({
          key: `${init?.method ?? 'GET'} ${url}`,
          release: (body, status = 200) =>
            resolve(
              new Response(JSON.stringify(body), {
                status,
                headers: { 'Content-Type': 'application/json' },
              }),
            ),
        })
      }),
  )
  return { fetch, calls }
}

describe('fromProfile / toBody', () => {
  it('keeps the preference override row as a preference row, not a mapping', () => {
    const doc = fromProfile(editableProfile())
    const row = doc.modes[1]!.mappings[0]!
    expect(row.kind).toBe('preference')
    expect(row.output).toBe('mouse_speed')
    expect(row.value).toBe('150')

    const body = toBody(doc)
    const sent = body.modes![1]!.mappings[0]!
    expect(sent.kind).toBe('preference')
    expect(sent.output).toBe('mouse_speed')
    expect(sent.value).toBe('150')
    // a preference row must not carry inputs or params, which the API rejects
    expect(sent.inputs).toBeUndefined()
    expect(sent.params).toBeUndefined()
  })

  it("round-trips a sequence row's inputs in order", () => {
    const doc = fromProfile(editableProfile())
    const seq = doc.modes[0]!.mappings[2]!
    expect(seq.inputs).toEqual(['mp_left_sip', 'mp_right_sip'])
    expect(toBody(doc).modes![0]!.mappings[2]!.inputs).toEqual(['mp_left_sip', 'mp_right_sip'])
  })

  it('gives every mode and row a key, so the UI survives a reorder', () => {
    const doc = fromProfile(editableProfile())
    const keys = [...doc.modes.map((m) => m.key), ...doc.modes.flatMap((m) => m.mappings.map((r) => r.key))]
    expect(new Set(keys).size).toBe(keys.length)
  })

  it('carries firmware, which the sheet never had, and nothing the file cannot hold', () => {
    const body = toBody(fromProfile(editableProfile()))
    expect(body.firmware).toBe(2373)
    // the emulation mode lives in the file's own preference row and each mode has its
    // own channel, so neither is a profile attribute any more
    expect(body).not.toHaveProperty('emulation_mode')
    expect(body).not.toHaveProperty('channel')
  })

  it('keeps the emulation mode as the enable_DS3_emulation preference row', () => {
    const doc = fromProfile(editableProfile({ preferences: { enable_DS3_emulation: '6' } }))
    expect(doc.preferences.enable_DS3_emulation).toBe('6')
    expect(toBody(doc).preferences?.enable_DS3_emulation).toBe('6')
  })
})

describe('document store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.unstubAllGlobals()
  })

  it('loads, selects the first mode, and checks without saving', async () => {
    const fetchMock = stubFetch(routes())
    vi.stubGlobal('fetch', fetchMock)
    const store = useDocumentStore()
    await store.load(1)
    expect(store.doc?.name).toBe('ddfortnite')
    expect(store.selectedMode?.name).toBe('Left')
    expect(store.selectedModeNumber).toBe(1)
    expect(store.validation?.budget?.modes_max).toBe(16)
    expect(store.dirty).toBe(false)
    // the check is the stateless endpoint; nothing was PUT
    expect(fetchMock.mock.calls.some((c) => String(c[0]).endsWith('/profiles/validate'))).toBe(true)
    expect(fetchMock.mock.calls.some((c) => c[1]?.method === 'PUT')).toBe(false)
  })

  it('becomes dirty on an edit and clean again after a save', async () => {
    const store = await loaded({ 'PUT /api/profiles/1': editableProfile({ name: 'Renamed' }) })
    store.doc!.name = 'Renamed'
    expect(store.dirty).toBe(true)
    expect(await store.save()).toBe(true)
    expect(store.doc?.name).toBe('Renamed')
    expect(store.dirty).toBe(false)
  })

  it('selected mode survives save()', async () => {
    const store = await loaded({ 'PUT /api/profiles/1': editableProfile({ name: 'Renamed' }) })
    store.selectMode(store.doc!.modes[1]!.key)
    expect(store.selectedModeNumber).toBe(2)
    store.doc!.name = 'Renamed'
    expect(await store.save()).toBe(true)
    // the reply is re-keyed, so the old key is gone; the position must not be
    expect(store.selectedModeNumber).toBe(2)
    expect(store.selectedMode?.name).toBe('Right')
    expect(store.selectedModeKey).toBe(store.doc!.modes[1]!.key)
  })

  it('reverts to the last saved state', async () => {
    const store = await loaded()
    store.doc!.name = 'Scratch'
    store.doc!.modes[0]!.mappings.pop()
    expect(store.dirty).toBe(true)
    store.revert()
    expect(store.doc?.name).toBe('ddfortnite')
    expect(store.doc?.modes[0]?.mappings).toHaveLength(3)
    expect(store.dirty).toBe(false)
  })

  it('keeps keys unique after a revert, so the UI does not reuse stale ones', async () => {
    const store = await loaded()
    const before = store.doc!.modes[0]!.key
    store.doc!.name = 'Scratch'
    store.revert()
    const after = store.doc!.modes[0]!.key
    expect(after).not.toBe(before)
    const keys = store.doc!.modes.flatMap((m) => [m.key, ...m.mappings.map((r) => r.key)])
    expect(new Set(keys).size).toBe(keys.length)
  })

  it('revert restores full row shape for preference rows', async () => {
    // The saved body carries a preference row as {kind, output, value, comment} only.
    // The views iterate inputs/params on every row, so a revert that hands back the
    // bare wire shape blanks the editor with a TypeError.
    const store = await loaded()
    store.selectMode(store.doc!.modes[1]!.key)
    store.doc!.name = 'Scratch'
    store.revert()
    const pref = store.doc!.modes[1]!.mappings[0]!
    expect(pref.kind).toBe('preference')
    expect(pref.output).toBe('mouse_speed')
    expect(pref.value).toBe('150')
    expect(pref.inputs).toEqual([])
    expect(pref.params).toEqual([])
    expect(pref.function).toBe('normal')
    expect(typeof pref.key).toBe('string')
    // every row, not only the preference one, comes back whole
    for (const m of store.doc!.modes) {
      for (const r of m.mappings) {
        expect(Array.isArray(r.inputs)).toBe(true)
        expect(Array.isArray(r.params)).toBe(true)
        expect(typeof r.function).toBe('string')
        expect(typeof r.value).toBe('string')
      }
    }
    // a stale key would leave the rail highlighting nothing
    expect(store.selectedModeKey).toBe(store.doc!.modes[0]!.key)
    expect(store.dirty).toBe(false)
  })

  it('reports a failed save without losing the edit', async () => {
    const store = await loaded({
      'PUT /api/profiles/1': { status: 422, body: JSON.stringify({ detail: 'bad filename' }) },
    })
    store.doc!.csv_filename = 'bad name.csv'
    expect(await store.save()).toBe(false)
    expect(store.error).toContain('bad filename')
    expect(store.doc?.csv_filename).toBe('bad name.csv') // still there to fix
    expect(store.dirty).toBe(true)
  })
})

describe('modes', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.unstubAllGlobals()
  })

  it('reorders with buttons, and the position is the mode number', async () => {
    const store = await loaded()
    expect(store.doc!.modes.map((m) => m.name)).toEqual(['Left', 'Right'])
    const rightKey = store.doc!.modes[1]!.key
    store.moveMode(rightKey, -1)
    expect(store.doc!.modes.map((m) => m.name)).toEqual(['Right', 'Left'])
    // the renumbering is what gets sent, so mode 1 is now Right
    expect(toBody(store.doc!).modes![0]!.name).toBe('Right')
  })

  it('will not move a mode off either end', async () => {
    const store = await loaded()
    const first = store.doc!.modes[0]!.key
    const last = store.doc!.modes[1]!.key
    store.moveMode(first, -1)
    store.moveMode(last, 1)
    expect(store.doc!.modes.map((m) => m.name)).toEqual(['Left', 'Right'])
  })

  it('refuses to add past the firmware limit', async () => {
    const store = await loaded()
    for (let i = 0; i < 20; i++) store.addMode(`M${i}`, 16)
    expect(store.doc!.modes).toHaveLength(16)
  })

  it('keeps a mode selected after deleting the selected one', async () => {
    const store = await loaded()
    const firstKey = store.doc!.modes[0]!.key
    store.deleteMode(firstKey)
    expect(store.doc!.modes).toHaveLength(1)
    expect(store.selectedModeKey).toBe(store.doc!.modes[0]!.key)
    expect(store.selectedMode?.name).toBe('Right')
  })

  it('renames a mode', async () => {
    const store = await loaded()
    store.renameMode(store.doc!.modes[0]!.key, 'Driving')
    expect(store.doc!.modes[0]!.name).toBe('Driving')
  })
})

describe('mappings', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.unstubAllGlobals()
  })

  it('buckets a sequence row on its LAST input, because that is when it fires', async () => {
    const store = await loaded()
    // the sequence is mp_left_sip then mp_right_sip
    expect(store.mappingsForInput('mp_right_sip').map((m) => m.output)).toEqual(['circle'])
    expect(store.mappingsForInput('mp_left_sip')).toEqual([])
  })

  it('ignores preference rows when listing what an input does', async () => {
    const store = await loaded()
    store.selectMode(store.doc!.modes[1]!.key)
    // mode 2 holds a preference override and one real mapping
    expect(store.mappingsForInput('right_puff').map((m) => m.output)).toEqual(['decrement_mode'])
    for (const input of ['mouse_speed', '']) expect(store.mappingsForInput(input)).toEqual([])
  })

  it('adds, updates and deletes a row', async () => {
    const store = await loaded()
    const modeKey = store.doc!.modes[0]!.key
    const row = store.addMapping(modeKey, { inputs: ['lip'], output: 'square' })!
    expect(store.mappingsForInput('lip').map((m) => m.output)).toEqual(['square'])
    store.updateMapping(modeKey, row.key, { function: 'repeat', params: [5, 2000] })
    expect(store.mappingsForInput('lip')[0]!.function).toBe('repeat')
    store.deleteMapping(modeKey, row.key)
    expect(store.mappingsForInput('lip')).toEqual([])
  })

  it('sends a new row in the shape the API accepts', async () => {
    const store = await loaded()
    store.addMapping(store.doc!.modes[0]!.key, { inputs: ['lip'], output: 'square' })
    const sent = toBody(store.doc!).modes![0]!.mappings.at(-1)!
    expect(sent).toMatchObject({ kind: 'mapping', output: 'square', inputs: ['lip'], function: 'normal' })
  })
})

describe('labels and findings', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.unstubAllGlobals()
  })

  it('prefers a per-mode game action over the profile-wide one', async () => {
    const store = await loaded()
    expect(store.actionFor('x')).toBe('Jump')
    store.setAction('x', 'Jump higher', 'Left')
    expect(store.actionFor('x', 'Left')).toBe('Jump higher')
    expect(store.actionFor('x', 'Right')).toBe('Jump') // falls back to the profile-wide label
  })

  it('removes a game action when the label is cleared', async () => {
    const store = await loaded()
    store.setAction('x', '')
    expect(store.actionFor('x')).toBeNull()
    expect(store.doc!.game_actions).toHaveLength(0)
  })

  it("uses the profile's own name for an input", async () => {
    const store = await loaded()
    expect(store.inputName('lip', 'Lip button')).toBe('Chin switch')
    expect(store.inputName('right_sip', 'Side tube sip')).toBe('Side tube sip')
    store.setInputName('lip', '')
    expect(store.inputName('lip', 'Lip button')).toBe('Lip button')
  })

  it('carries a rename onto the soft variant of the same physical input', async () => {
    const store = await loaded()
    // lip is renamed "Chin switch"; lip_soft is the same button pressed gently, so
    // it must not keep reading "Lip button (soft)" next to it
    expect(store.inputName('lip_soft', 'Lip button (soft)')).toBe('Chin switch (soft)')
    // an explicit name for the soft one still wins
    store.setInputName('lip_soft', 'Chin tap')
    expect(store.inputName('lip_soft', 'Lip button (soft)')).toBe('Chin tap')
    // and with no rename at all, the catalog label stands
    store.setInputName('lip', '')
    store.setInputName('lip_soft', '')
    expect(store.inputName('lip_soft', 'Lip button (soft)')).toBe('Lip button (soft)')
  })

  it('drops a preference rather than sending an empty string', async () => {
    const store = await loaded()
    expect(store.doc!.preferences.mouse_speed).toBe('100')
    store.setPreference('mouse_speed', '')
    expect('mouse_speed' in store.doc!.preferences).toBe(false)
  })

  it('splits findings into per-mode and file-level', async () => {
    const store = await loaded()
    store.validation = validation({
      errors: 1,
      warnings: 2,
      findings: [
        { severity: 'error', mode: 1, row: 4, message: 'row problem' },
        { severity: 'warning', mode: 2, row: null, message: 'mode problem' },
        { severity: 'warning', mode: null, row: null, message: 'file problem' },
      ],
      consequence: { error: 'will not read', warning: 'still loads' },
    })
    expect(store.findingsFor(1).map((f) => f.message)).toEqual(['row problem'])
    expect(store.findingsFor(2).map((f) => f.message)).toEqual(['mode problem'])
    expect(store.fileFindings.map((f) => f.message)).toEqual(['file problem'])
    expect(store.worst).toBe('error')
    expect(store.canExport).toBe(false)
  })

  it('allows export with warnings but not with errors', async () => {
    const store = await loaded()
    store.validation = validation({ warnings: 5 })
    expect(store.canExport).toBe(true)
    expect(store.worst).toBe('warning')
    store.validation = validation({ errors: 1 })
    expect(store.canExport).toBe(false)
  })

  it('does not allow export until a check has answered', async () => {
    // the profile loads but the live check itself fails, so nothing is known yet
    vi.stubGlobal(
      'fetch',
      stubFetch(routes({ 'POST /api/profiles/validate': { status: 500, body: 'boom' } })),
    )
    const store = useDocumentStore()
    await store.load(1)
    expect(store.doc).not.toBeNull()
    expect(store.validation).toBeNull()
    expect(store.canExport).toBe(false)

    // a check that answers clean turns it on
    vi.stubGlobal('fetch', stubFetch(routes()))
    await store.check()
    expect(store.canExport).toBe(true)
  })
})

describe('live checks', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.unstubAllGlobals()
  })

  it('debounces, so typing does not fire a request per keystroke', async () => {
    vi.useFakeTimers()
    const fetchMock = stubFetch(routes())
    vi.stubGlobal('fetch', fetchMock)
    const store = useDocumentStore()
    await store.load(1)
    const before = fetchMock.mock.calls.filter((c) => String(c[0]).endsWith('/profiles/validate')).length

    for (const name of ['a', 'ab', 'abc', 'abcd']) store.doc!.name = name
    await Promise.resolve() // let the watcher run
    vi.advanceTimersByTime(100)
    const during = fetchMock.mock.calls.filter((c) => String(c[0]).endsWith('/profiles/validate')).length
    expect(during).toBe(before) // nothing yet

    vi.advanceTimersByTime(400)
    await Promise.resolve()
    const after = fetchMock.mock.calls.filter((c) => String(c[0]).endsWith('/profiles/validate')).length
    expect(after).toBe(before + 1) // one request for the whole burst
    vi.useRealTimers()
  })

  it('keeps the last good findings when a check is rejected', async () => {
    const store = await loaded()
    const good = store.validation
    expect(good).not.toBeNull()
    vi.stubGlobal(
      'fetch',
      stubFetch({
        'POST /api/profiles/validate': {
          status: 422,
          body: JSON.stringify({ detail: [{ loc: ['body', 'csv_filename'], msg: 'must end in .csv' }] }),
          headers: { 'Content-Type': 'application/json' },
        },
      }),
    )
    await store.check()
    expect(store.error).toContain('must end in .csv')
    expect(store.validation).toBe(good) // not wiped
  })

  it('a failed check followed by a success clears the banner', async () => {
    const store = await loaded()
    vi.stubGlobal(
      'fetch',
      stubFetch({
        'POST /api/profiles/validate': {
          status: 422,
          body: JSON.stringify({ detail: [{ loc: ['body', 'csv_filename'], msg: 'must end in .csv' }] }),
          headers: { 'Content-Type': 'application/json' },
        },
      }),
    )
    await store.check()
    expect(store.error).toContain('must end in .csv')

    vi.stubGlobal('fetch', stubFetch(routes()))
    await store.check()
    expect(store.error).toBeNull()
    expect(store.validation).not.toBeNull()
  })

  it('out-of-order responses keep the newest', async () => {
    const store = await loaded()
    const { fetch, calls } = deferredFetch()
    vi.stubGlobal('fetch', fetch)

    const older = store.check()
    const newer = store.check()
    expect(calls).toHaveLength(2)

    // the newer request answers first
    calls[1]!.release(validation({ warnings: 7 }))
    await newer
    expect(store.validation?.warnings).toBe(7)
    expect(store.checking).toBe(false)

    // ...and the older one, arriving late, must not overwrite it
    calls[0]!.release(validation({ errors: 3 }))
    await older
    expect(store.validation?.warnings).toBe(7)
    expect(store.validation?.errors).toBe(0)
    expect(store.canExport).toBe(true)
    expect(store.checking).toBe(false)
  })

  it('a late failure from an older check does not raise the banner', async () => {
    const store = await loaded()
    const { fetch, calls } = deferredFetch()
    vi.stubGlobal('fetch', fetch)

    const older = store.check()
    const newer = store.check()
    calls[1]!.release(validation())
    await newer
    calls[0]!.release({ detail: 'boom' }, 500)
    await older
    expect(store.error).toBeNull()
  })

  it('a slower earlier load cannot overwrite a newer one', async () => {
    const { fetch, calls } = deferredFetch()
    vi.stubGlobal('fetch', fetch)
    const store = useDocumentStore()

    const first = store.load(1)
    const second = store.load(2)
    expect(calls.map((c) => c.key)).toEqual(['GET /api/profiles/1', 'GET /api/profiles/2'])

    // profile 2 answers first, then its check
    calls[1]!.release(editableProfile({ id: 2, name: 'Other' }))
    await vi.waitFor(() => expect(calls).toHaveLength(3))
    expect(calls[2]!.key).toBe('POST /api/profiles/validate')
    calls[2]!.release(validation({ budget: budget() }))
    await second
    expect(store.id).toBe(2)
    expect(store.doc?.name).toBe('Other')
    expect(store.loading).toBe(false)

    // profile 1 arrives late: ignored, and it does not even run a check
    calls[0]!.release(editableProfile())
    await first
    expect(store.id).toBe(2)
    expect(store.doc?.name).toBe('Other')
    expect(store.loading).toBe(false)
    expect(calls).toHaveLength(3)
  })
})
