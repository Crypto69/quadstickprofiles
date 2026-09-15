import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import LibraryView from './LibraryView.vue'
import { catalog, conflict, fileResponse, noContent, profile, stubFetch, summary, validation } from '@/test/factories'

const RouterLinkStub = {
  props: ['to'],
  template: '<a :href="String(to)"><slot /></a>',
}

function mountLibrary() {
  return mount(LibraryView, {
    attachTo: document.body,
    global: { stubs: { RouterLink: RouterLinkStub } },
  })
}

/** Find a button by its visible label, anywhere including teleported dialogs. */
function button(label: string) {
  return [...document.body.querySelectorAll('button')].find((b) =>
    (b.textContent ?? '').trim().includes(label),
  )
}

async function settle(times = 6) {
  for (let i = 0; i < times; i++) await Promise.resolve()
  await new Promise((r) => setTimeout(r, 0))
}

describe('LibraryView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.unstubAllGlobals()
    document.body.innerHTML = ''
  })

  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('lists profiles with their facts and validation badge', async () => {
    vi.stubGlobal(
      'fetch',
      stubFetch({
        '/api/catalog': catalog(),
        '/api/profiles?templates=true': [],
        '/api/profiles?validate=true': [
          summary({ validation: validation({ warnings: 2 }) }),
          summary({ id: 2, name: 'Call of Duty', csv_filename: 'cod.csv', game: 'Call of Duty', mode_count: 8 }),
        ],
      }),
    )
    const w = mountLibrary()
    await settle()
    const text = w.text()
    expect(text).toContain('ddfortnite')
    expect(text).toContain('ddfortnite.csv')
    expect(text).toContain('7 modes')
    expect(text).toContain('PlayStation names')
    expect(text).toContain('2 warnings')
    expect(text).toContain('Call of Duty')
    w.unmount()
  })

  it('offers a conversion to the other naming set, not the one it already uses', async () => {
    vi.stubGlobal(
      'fetch',
      stubFetch({
        '/api/catalog': catalog(),
        '/api/profiles?templates=true': [],
        '/api/profiles?validate=true': [
          summary({ console: 'playstation' }),
          summary({ id: 2, name: 'COD Xbox', csv_filename: 'codxbox.csv', console: 'xbox' }),
        ],
      }),
    )
    const w = mountLibrary()
    await settle()
    expect(w.text()).toContain('To Xbox')
    expect(w.text()).toContain('To PlayStation')
    w.unmount()
  })

  it('warns on a profile whose emulation mode hides the flash drive', async () => {
    vi.stubGlobal(
      'fetch',
      stubFetch({
        '/api/catalog': catalog(),
        '/api/profiles?templates=true': [],
        '/api/profiles?validate=true': [
          summary({ emulation_mode: 6, firmware: 2373 }),
          summary({ id: 2, name: 'Safe', csv_filename: 'safe.csv', emulation_mode: 4, firmware: 2373 }),
        ],
      }),
    )
    const w = mountLibrary()
    await settle()
    const warnings = w.findAll('.drive-warning')
    expect(warnings).toHaveLength(1)
    expect(warnings[0]!.text()).toContain('mode 6 hides the flash drive')
    expect(warnings[0]!.text()).toContain('2373')
    w.unmount()
  })

  it('says it cannot tell, rather than nothing, on a firmware the catalog does not know', async () => {
    vi.stubGlobal(
      'fetch',
      stubFetch({
        '/api/catalog': catalog(),
        '/api/profiles?templates=true': [],
        '/api/profiles?validate=true': [summary({ emulation_mode: 4, firmware: 9999 })],
      }),
    )
    const w = mountLibrary()
    await settle()
    const warnings = w.findAll('.drive-warning')
    expect(warnings).toHaveLength(1)
    const text = warnings[0]!.text()
    expect(text).toMatch(/cannot tell\s+whether the flash drive stays visible/i)
    expect(text).toContain('9999')
    expect(text).toContain('emulation mode 4')
    expect(text).not.toContain('hides the flash drive')
    w.unmount()
  })

  it('shows the import findings after an import, and the profile it made', async () => {
    const findings = validation({
      warnings: 1,
      findings: [{ severity: 'warning', mode: null, row: null, message: 'Reference Card is stale' }],
      consequence: { warning: 'The QuadStick still loads this profile, but…' },
    })
    vi.stubGlobal(
      'fetch',
      stubFetch({
        '/api/catalog': catalog(),
        '/api/profiles?templates=true': [],
        '/api/profiles?validate=true': [summary()],
        'POST /api/profiles/import': { profile: profile({ modes: [] }), findings },
      }),
    )
    const w = mountLibrary()
    await settle()
    const store = (await import('@/stores/profiles')).useProfilesStore()
    await store.importFile(new File(['x'], 'ddfortnite.csv'))
    await settle()
    expect(document.body.textContent).toContain('Reference Card is stale')
    expect(document.body.textContent).toContain('still loads this profile')
    w.unmount()
  })

  it('explains a refused export instead of failing silently', async () => {
    // The list said clean when it loaded, but the API re-checks on export and refuses:
    // the button was enabled, so the refusal has to be explained.
    const v = validation({
      errors: 1,
      findings: [{ severity: 'error', mode: 2, row: 9, message: "Unknown output 'nope'" }],
      consequence: { error: 'The QuadStick will not read this profile correctly.' },
    })
    vi.stubGlobal(
      'fetch',
      stubFetch({
        '/api/catalog': catalog(),
        '/api/profiles?templates=true': [],
        '/api/profiles?validate=true': [summary()],
        '/api/profiles/1/export.csv': conflict('Export refused: fix the validation errors first', v),
      }),
    )
    const w = mountLibrary()
    await settle()
    button('Export CSV')!.click()
    await settle()
    expect(document.body.textContent).toContain('Export refused')
    expect(document.body.textContent).toContain("Unknown output 'nope'")
    expect(document.body.textContent).toContain('Mode 2, row 9')
    w.unmount()
  })

  it('disables Export for a profile with errors, and says why', async () => {
    const v = validation({
      errors: 1,
      findings: [{ severity: 'error', mode: 1, row: 4, message: "Unknown output 'nope'" }],
    })
    vi.stubGlobal(
      'fetch',
      stubFetch({
        '/api/catalog': catalog(),
        '/api/profiles?templates=true': [],
        '/api/profiles?validate=true': [
          summary({ validation: v }),
          summary({ id: 2, name: 'Clean', csv_filename: 'clean.csv' }),
          summary({ id: 3, name: 'Unchecked', csv_filename: 'unchecked.csv', validation: null }),
        ],
      }),
    )
    const w = mountLibrary()
    await settle()
    const exports = w.findAll('button').filter((b) => b.text() === 'Export CSV')
    expect(exports).toHaveLength(3)
    expect(exports[0]!.attributes('disabled')).toBeDefined()
    expect(exports[0]!.attributes('title')).toMatch(/fix the errors first/i)
    // a clean profile, and one the API has not checked, both stay exportable
    expect(exports[1]!.attributes('disabled')).toBeUndefined()
    expect(exports[1]!.attributes('title')).toBe('')
    expect(exports[2]!.attributes('disabled')).toBeUndefined()
    w.unmount()
  })

  it('hands the file over and then shows the install checklist', async () => {
    const click = vi.fn()
    const orig = document.createElement.bind(document)
    vi.spyOn(document, 'createElement').mockImplementation((tag: string) => {
      const el = orig(tag) as HTMLElement
      if (tag === 'a') el.click = click
      return el
    })
    vi.stubGlobal(
      'fetch',
      stubFetch({
        '/api/catalog': catalog(),
        '/api/profiles?templates=true': [],
        '/api/profiles?validate=true': [summary()],
        '/api/profiles/1/export.csv': fileResponse('QuadStick Configuration,Version 1.4,,x\r\n', {
          filename: 'ddfortnite.csv',
          contentType: 'text/csv',
          exportPath: '/app/exports/ddfortnite.csv',
        }),
      }),
    )
    const w = mountLibrary()
    await settle()
    button('Export CSV')!.click()
    await settle()
    expect(click).toHaveBeenCalled() // the download happened
    expect(document.body.textContent).toContain('Put this profile on the QuadStick')
    expect(document.body.textContent).toContain('default.csv')
    w.unmount()
  })

  it('asks before deleting, and only deletes on confirmation', async () => {
    const fetchMock = stubFetch({
      '/api/catalog': catalog(),
      '/api/profiles?templates=true': [],
      '/api/profiles?validate=true': [summary()],
      'DELETE /api/profiles/1': noContent(),
    })
    vi.stubGlobal('fetch', fetchMock)
    const w = mountLibrary()
    await settle()

    button('Delete')!.click()
    await settle()
    expect(document.body.textContent).toContain('Delete this profile?')
    expect(fetchMock.mock.calls.some((c) => c[1]?.method === 'DELETE')).toBe(false)

    button('Keep it')!.click()
    await settle()
    expect(fetchMock.mock.calls.some((c) => c[1]?.method === 'DELETE')).toBe(false)

    button('Delete')!.click()
    await settle()
    // the dialog's own confirm button, not the row's
    const confirm = [...document.body.querySelectorAll('footer button')].find((b) =>
      (b.textContent ?? '').trim() === 'Delete',
    ) as HTMLButtonElement
    confirm.click()
    await settle()
    expect(fetchMock.mock.calls.some((c) => c[1]?.method === 'DELETE')).toBe(true)
    w.unmount()
  })

  it.each([
    ['Print detailed sheets', '/api/profiles/1/card.html'],
    ['Print summary', '/api/profiles/1/summary.html'],
  ])('opens %s in its own tab, from the API not the SPA route', async (label, url) => {
    const openSpy = vi.fn()
    vi.stubGlobal('open', openSpy)
    vi.stubGlobal(
      'fetch',
      stubFetch({
        '/api/catalog': catalog(),
        '/api/profiles?templates=true': [],
        '/api/profiles?validate=true': [summary()],
      }),
    )
    const w = mountLibrary()
    await settle()
    button(label)!.click()
    await settle()
    expect(openSpy).toHaveBeenCalledWith(url, '_blank', 'noopener')
    w.unmount()
  })

  it('sends the print pages to the system browser in the desktop build', async () => {
    const openSpy = vi.fn()
    vi.stubGlobal('open', openSpy)
    const open_external = vi.fn().mockResolvedValue(undefined)
    window.pywebview = { api: { reveal: vi.fn(), open_external } }
    vi.stubGlobal(
      'fetch',
      stubFetch({
        '/api/catalog': catalog(),
        '/api/profiles?templates=true': [],
        '/api/profiles?validate=true': [summary()],
      }),
    )
    const w = mountLibrary()
    await settle()
    button('Print detailed sheets')!.click()
    await settle()
    expect(open_external).toHaveBeenCalledWith(`${window.location.origin}/api/profiles/1/card.html`)
    expect(openSpy).not.toHaveBeenCalled()
    delete window.pywebview
    w.unmount()
  })

  it('invites an import when the library is empty', async () => {
    vi.stubGlobal(
      'fetch',
      stubFetch({
        '/api/catalog': catalog(),
        '/api/profiles?templates=true': [],
        '/api/profiles?validate=true': [],
      }),
    )
    const w = mountLibrary()
    await settle()
    expect(w.text()).toContain('Nothing here yet')
    expect(w.text()).toContain('.xlsx')
    expect(w.text()).toContain('.csv')
    w.unmount()
  })

  it('offers the starter profiles when creating a new one', async () => {
    vi.stubGlobal(
      'fetch',
      stubFetch({
        '/api/catalog': catalog(),
        '/api/profiles?validate=true': [summary()],
        '/api/profiles?templates=true': [
          summary({
            id: 10, name: 'Fortnite starter', game: 'Fortnite', is_template: true,
            template_note: 'Seven modes built around the sticks', mode_count: 7,
          }),
          summary({
            id: 11, name: 'Xbox-named starter', game: 'Call of Duty', console: 'xbox',
            is_template: true, template_note: 'Five modes, Xbox names', mode_count: 5,
          }),
        ],
      }),
    )
    const w = mountLibrary()
    await settle()
    button('New profile')!.click()
    await settle()
    const text = document.body.textContent ?? ''
    // blank is offered first, then each starter with what it is for
    expect(text).toContain('Start from')
    expect(text).toContain('Nothing')
    expect(text).toContain('Fortnite starter')
    expect(text).toContain('Seven modes built around the sticks')
    expect(text).toContain('Xbox-named starter')
    expect(text).toContain('Xbox names')
    w.unmount()
  })

  it('creates from a starter, and prefills the name from it', async () => {
    const fetchMock = stubFetch({
      '/api/catalog': catalog(),
      '/api/profiles?validate=true': [summary()],
      '/api/profiles?templates=true': [
        summary({ id: 10, name: 'Fortnite starter', game: 'Fortnite', is_template: true,
                  template_note: 'Seven modes', mode_count: 7 }),
      ],
      'POST /api/profiles/from-template/10': profile({ id: 20, name: 'Fortnite' }),
    })
    vi.stubGlobal('fetch', fetchMock)
    const w = mountLibrary()
    await settle()
    button('New profile')!.click()
    await settle()

    // choosing a starter fills in the name, so one more click is enough
    const radios = [...document.body.querySelectorAll<HTMLInputElement>('input[name="start"]')]
    expect(radios).toHaveLength(2) // nothing + one starter
    radios[1]!.checked = true
    radios[1]!.dispatchEvent(new Event('change'))
    await settle()
    const name = document.body.querySelector<HTMLInputElement>('#np-name')!
    expect(name.value).toBe('Fortnite')

    button('Create')!.click()
    await settle()
    const call = fetchMock.mock.calls.find((c) => String(c[0]).includes('from-template/10'))
    expect(call).toBeTruthy()
    expect(JSON.parse(String(call![1]!.body))).toMatchObject({
      name: 'Fortnite', csv_filename: 'fortnite.csv',
    })
    w.unmount()
  })

  it('creates a blank profile when nothing is chosen', async () => {
    const fetchMock = stubFetch({
      '/api/catalog': catalog(),
      '/api/profiles?validate=true': [summary()],
      '/api/profiles?templates=true': [],
      'POST /api/profiles': profile({ id: 21, name: 'Empty' }),
    })
    vi.stubGlobal('fetch', fetchMock)
    const w = mountLibrary()
    await settle()
    button('New profile')!.click()
    await settle()
    const name = document.body.querySelector<HTMLInputElement>('#np-name')!
    name.value = 'Empty'
    name.dispatchEvent(new Event('input'))
    await settle()
    button('Create')!.click()
    await settle()
    // the plain create endpoint, not from-template
    expect(fetchMock.mock.calls.some((c) => String(c[0]).endsWith('/api/profiles') && c[1]?.method === 'POST')).toBe(true)
    expect(fetchMock.mock.calls.some((c) => String(c[0]).includes('from-template'))).toBe(false)
    w.unmount()
  })

  it('keeps the starters off the library shelf', async () => {
    vi.stubGlobal(
      'fetch',
      stubFetch({
        '/api/catalog': catalog(),
        // the API filters, so the library request never returns a template
        '/api/profiles?validate=true': [summary({ name: 'Mine' })],
        '/api/profiles?templates=true': [
          summary({ id: 10, name: 'A starter', is_template: true, template_note: 'x' }),
        ],
      }),
    )
    const w = mountLibrary()
    await settle()
    const rows = w.findAll('.profile h2').map((h) => h.text())
    expect(rows).toEqual(['Mine'])
    w.unmount()
  })

  it('distinguishes "no results" from "no profiles"', async () => {
    vi.stubGlobal(
      'fetch',
      stubFetch({
        '/api/catalog': catalog(),
        '/api/profiles?templates=true': [],
        '/api/profiles?validate=true': [],
        '/api/profiles?q=zzz&validate=true': [],
      }),
    )
    const w = mountLibrary()
    await settle()
    const store = (await import('@/stores/profiles')).useProfilesStore()
    store.search = 'zzz'
    await store.load()
    await settle()
    expect(w.text()).toContain('No profile matches')
    expect(w.text()).not.toContain('Nothing here yet')
    w.unmount()
  })

  // ---------------------------------------------------------------- filters
  /** Three profiles spanning both consoles and both emulation modes the catalog knows. */
  function mixedLibrary() {
    return stubFetch({
      '/api/catalog': catalog(),
      '/api/profiles?templates=true': [],
      '/api/profiles?validate=true': [
        summary({ id: 1, name: 'PS four', console: 'playstation', emulation_mode: 4 }),
        summary({ id: 2, name: 'PS six', console: 'playstation', emulation_mode: 6 }),
        summary({ id: 3, name: 'Xbox four', console: 'xbox', emulation_mode: 4 }),
      ],
    })
  }

  /**
   * Click a filter chip by its visible label. Matched on the label span alone, and
   * exactly: the chip's own text also carries the count, and "PS4 / PS5" is a prefix
   * of "PS4 / PS5, no drive", so a loose match would tick the wrong one.
   */
  async function tick(w: ReturnType<typeof mountLibrary>, label: string) {
    const chip = w
      .findAll('.chip')
      .find((c) => c.findAll('span').some((s) => s.text() === label))
    if (!chip) throw new Error(`no filter chip labelled ${label}`)
    await chip.find('input').setValue(true)
    await settle()
  }

  function names(w: ReturnType<typeof mountLibrary>) {
    return w.findAll('.profile h2').map((h) => h.text())
  }

  /** The visible label of every filter chip on offer, in document order. */
  function chipLabels(w: ReturnType<typeof mountLibrary>) {
    return w.findAll('.chip').map((c) => c.find('span').text())
  }

  it('narrows the list by button names', async () => {
    vi.stubGlobal('fetch', mixedLibrary())
    const w = mountLibrary()
    await settle()
    expect(names(w)).toHaveLength(3)
    await tick(w, 'Xbox')
    expect(names(w)).toEqual(['Xbox four'])
    w.unmount()
  })

  it('narrows the list by device, using the short label', async () => {
    vi.stubGlobal('fetch', mixedLibrary())
    const w = mountLibrary()
    await settle()
    await tick(w, 'PS4 / PS5, no drive')
    expect(names(w)).toEqual(['PS six'])
    w.unmount()
  })

  it('ANDs across groups but ORs within one', async () => {
    vi.stubGlobal('fetch', mixedLibrary())
    const w = mountLibrary()
    await settle()
    // Both device modes ticked = every profile that has either.
    await tick(w, 'PS4 / PS5, no drive')
    await tick(w, 'PS4 / PS5')
    expect(names(w)).toHaveLength(3)
    // Adding a console narrows it, because the groups combine with AND.
    await tick(w, 'PlayStation')
    expect(names(w)).toEqual(['PS four', 'PS six'])
    w.unmount()
  })

  it('counts ignore the chip’s own group, so a sibling never reads as zero', async () => {
    vi.stubGlobal('fetch', mixedLibrary())
    const w = mountLibrary()
    await settle()
    await tick(w, 'PlayStation')
    const xbox = w.findAll('.chip').find((c) => c.text().includes('Xbox'))
    // Ticking PlayStation must not make the Xbox chip claim there are no Xbox profiles.
    expect(xbox?.find('.count').text()).toBe('1')
    w.unmount()
  })

  it('hides a profile with no emulation mode from every device filter', async () => {
    vi.stubGlobal(
      'fetch',
      stubFetch({
        '/api/catalog': catalog(),
        '/api/profiles?templates=true': [],
        '/api/profiles?validate=true': [
          summary({ id: 1, name: 'Known', emulation_mode: 4 }),
          // A second mode, so the Device group has something to narrow and appears.
          summary({ id: 2, name: 'Other', emulation_mode: 6 }),
          summary({ id: 3, name: 'Unknown', emulation_mode: null }),
        ],
      }),
    )
    const w = mountLibrary()
    await settle()
    expect(names(w)).toHaveLength(3)
    await tick(w, 'PS4 / PS5')
    expect(names(w)).toEqual(['Known'])
    w.unmount()
  })

  it('offers only the devices some profile actually uses', async () => {
    vi.stubGlobal('fetch', mixedLibrary())
    const w = mountLibrary()
    await settle()
    const labels = chipLabels(w)
    // The catalog knows modes 4 and 6; the fixtures use both, and no others exist.
    expect(labels).toContain('PS4 / PS5')
    expect(labels).toContain('PS4 / PS5, no drive')
    // No chip may read zero — every one offered must lead somewhere.
    for (const chip of w.findAll('.chip')) {
      expect(chip.find('.count').text()).not.toBe('0')
    }
    w.unmount()
  })

  it('drops a group that cannot narrow anything', async () => {
    vi.stubGlobal(
      'fetch',
      stubFetch({
        '/api/catalog': catalog(),
        '/api/profiles?templates=true': [],
        // Both PlayStation, both mode 4: neither group can split them, so no bar.
        '/api/profiles?validate=true': [
          summary({ id: 1, name: 'One', console: 'playstation', emulation_mode: 4 }),
          summary({ id: 2, name: 'Two', console: 'playstation', emulation_mode: 4 }),
        ],
      }),
    )
    const w = mountLibrary()
    await settle()
    expect(w.find('.filters').exists()).toBe(false)
    expect(names(w)).toHaveLength(2)
    w.unmount()
  })

  it('keeps the Device group when only the consoles differ', async () => {
    vi.stubGlobal(
      'fetch',
      stubFetch({
        '/api/catalog': catalog(),
        '/api/profiles?templates=true': [],
        '/api/profiles?validate=true': [
          summary({ id: 1, name: 'PS', console: 'playstation', emulation_mode: 4 }),
          summary({ id: 2, name: 'XB', console: 'xbox', emulation_mode: 4 }),
        ],
      }),
    )
    const w = mountLibrary()
    await settle()
    const legends = w.findAll('.group legend').map((l) => l.text())
    expect(legends).toEqual(['Button names'])
    w.unmount()
  })

  it('offers a way back when the filters hide everything', async () => {
    vi.stubGlobal('fetch', mixedLibrary())
    const w = mountLibrary()
    await settle()
    // Xbox exists, but no Xbox profile uses mode 6 — an empty combination the user
    // can reach by ticking two boxes that each look fruitful on their own.
    await tick(w, 'Xbox')
    await tick(w, 'PS4 / PS5, no drive')
    expect(names(w)).toHaveLength(0)
    expect(w.text()).toContain('No profile matches the filters')
    expect(w.text()).not.toContain('Nothing here yet')

    const clear = w.findAll('button').find((b) => b.text().includes('Clear filters'))
    await clear?.trigger('click')
    await settle()
    expect(names(w)).toHaveLength(3)
    w.unmount()
  })

  it('keeps a ticked chip on offer after it stops matching', async () => {
    vi.stubGlobal('fetch', mixedLibrary())
    const w = mountLibrary()
    await settle()
    await tick(w, 'Xbox')
    await tick(w, 'PS4 / PS5, no drive')
    // Both are now zero-count, but yanking a ticked chip away would strand the user
    // with a filter applied and no control to undo it.
    const labels = chipLabels(w)
    expect(labels).toContain('Xbox')
    expect(labels).toContain('PS4 / PS5, no drive')
    w.unmount()
  })

  it('shows no filter bar when there is nothing to narrow', async () => {
    vi.stubGlobal(
      'fetch',
      stubFetch({
        '/api/catalog': catalog(),
        '/api/profiles?templates=true': [],
        '/api/profiles?validate=true': [summary()],
      }),
    )
    const w = mountLibrary()
    await settle()
    expect(w.find('.filters').exists()).toBe(false)
    w.unmount()
  })

  it('filters without asking the API again', async () => {
    const fetchSpy = vi.fn(mixedLibrary())
    vi.stubGlobal('fetch', fetchSpy)
    const w = mountLibrary()
    await settle()
    const before = fetchSpy.mock.calls.length
    await tick(w, 'Xbox')
    expect(fetchSpy.mock.calls.length).toBe(before)
    w.unmount()
  })
})
