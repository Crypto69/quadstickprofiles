import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h } from 'vue'
import { RouterView, createMemoryHistory, createRouter } from 'vue-router'
import EditorView from './EditorView.vue'
import DeviceView from '@/components/DeviceView.vue'
import { useDocumentStore } from '@/stores/document'
import { budget, catalog, conflict, editableProfile, prefs, stubFetch, validation } from '@/test/factories'

async function settle(times = 8) {
  for (let i = 0; i < times; i++) await Promise.resolve()
  await new Promise((r) => setTimeout(r, 0))
}

/** Find a button by its visible label, anywhere including teleported dialogs. */
function button(label: string) {
  return [...document.body.querySelectorAll('button')].find((b) =>
    (b.textContent ?? '').trim().includes(label),
  ) as HTMLButtonElement | undefined
}

/**
 * The editor lives under a real router: its route guards (leave, and the same-route
 * id change) only fire through a RouterView, so a bare mount would skip them.
 */
async function page(routes: Record<string, unknown> = {}) {
  const fetchMock = stubFetch({
    '/api/catalog': catalog(),
    '/api/prefs': prefs(),
    '/api/profiles/1': editableProfile(),
    'POST /api/profiles/validate': validation({ budget: budget({ modes_used: 2 }) }),
    ...routes,
  })
  vi.stubGlobal('fetch', fetchMock)
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: defineComponent({ render: () => h('p', 'library') }) },
      { path: '/profiles/:id', component: EditorView, props: true },
    ],
  })
  await router.push('/profiles/1')
  await router.isReady()
  const Host = defineComponent({ render: () => h(RouterView) })
  // Vue only logs a render error, so collect them here to assert nothing threw.
  const errors: unknown[] = []
  const w = mount(Host, {
    attachTo: document.body,
    global: { plugins: [router], config: { errorHandler: (e) => errors.push(e) } },
  })
  await settle()
  return { w, router, errors, fetchMock, docStore: useDocumentStore() }
}

describe('EditorView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.unstubAllGlobals()
    document.body.innerHTML = ''
  })
  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('loads the profile and lists the inputs it uses for renaming', async () => {
    const { w } = await page()
    expect(w.find('h1').text()).toBe('ddfortnite')
    button('Settings')!.click()
    await settle()
    // the used inputs, plus lip which is always offered; the preference row adds none
    const ids = [...document.body.querySelectorAll('input[id^="in-"]')].map((el) => el.id)
    expect(ids).toContain('in-mp_center_sip')
    expect(ids).toContain('in-right_puff')
    expect(ids).toContain('in-lip')
    expect(ids).not.toContain('in-mouse_speed')
    w.unmount()
  })

  // An info finding describes what the profile does. A correct profile has plenty,
  // so calling them problems told the owner their deliberate design was broken.
  const NOTE = {
    severity: 'info' as const,
    mode: 1,
    row: 24,
    message: "'lip' triggers left_2 AND increment_mode: the game action fires at the same moment the mode switches",
  }
  const WARN = {
    severity: 'warning' as const,
    mode: 4,
    row: null,
    message: 'Not connected by USB (C3 is bluetooth)',
  }

  it('does not call the strip Problems when only notes are left', async () => {
    const { w } = await page({
      'POST /api/profiles/validate': validation({ info: 1, findings: [NOTE] }),
    })
    expect(w.find('.problems-strip h2').text()).toBe('Nothing to fix')
    w.unmount()
  })

  it('keeps calling the strip Problems while a warning remains', async () => {
    const { w } = await page({
      'POST /api/profiles/validate': validation({ warnings: 1, findings: [WARN] }),
    })
    expect(w.find('.problems-strip h2').text()).toBe('Problems')
    w.unmount()
  })

  it('keeps notes out of the list of things to fix', async () => {
    const { w } = await page({
      'POST /api/profiles/validate': validation({
        warnings: 1,
        info: 1,
        findings: [WARN, NOTE],
      }),
    })
    // the top list holds the warning alone
    const top = w.findAll('.problems-strip > .problems li')
    expect(top).toHaveLength(1)
    expect(top[0]!.classes()).toContain('warning')
    // the note is under its own heading, which says there is nothing to fix in it
    const notes = w.find('.notes')
    expect(notes.text()).toContain('What this profile does')
    expect(notes.text()).toContain('nothing to fix')
    expect(notes.findAll('li')).toHaveLength(1)
    expect(notes.text()).toContain('the mode switches')
    w.unmount()
  })

  // Folded away while there is real work, open once the notes are all that is left.
  it('opens the notes only when there is nothing to fix', async () => {
    const { w } = await page({
      'POST /api/profiles/validate': validation({ info: 1, findings: [NOTE] }),
    })
    expect(w.find('.notes').attributes('open')).toBeDefined()
    w.unmount()

    const both = await page({
      'POST /api/profiles/validate': validation({ warnings: 1, info: 1, findings: [WARN, NOTE] }),
    })
    expect(both.w.find('.notes').attributes('open')).toBeUndefined()
    both.w.unmount()
  })

  // Pointing at a tube on the photo marks everything it drives, the open editor
  // included — otherwise the link stops at the edge of the picture.
  it('rings the editor pane when the hovered part owns the input it shows', async () => {
    const { w } = await page()
    const device = w.findComponent(DeviceView)
    device.vm.$emit('select', 'mp_left_sip')
    await settle()
    expect(w.find('.side').classes()).not.toContain('lit')

    device.vm.$emit('hover', ['mp_left_sip', 'mp_left_puff'])
    await settle()
    expect(w.find('.side').classes()).toContain('lit')

    // a different part leaves it alone
    device.vm.$emit('hover', ['lip', 'lip_soft'])
    await settle()
    expect(w.find('.side').classes()).not.toContain('lit')

    device.vm.$emit('hover', [])
    await settle()
    expect(w.find('.side').classes()).not.toContain('lit')
    w.unmount()
  })

  it('says the profile is fine when there is nothing at all', async () => {
    const { w } = await page({
      'POST /api/profiles/validate': validation({ findings: [] }),
    })
    expect(w.find('.problems-strip').text()).toContain('will load and behave as written')
    expect(w.find('.notes').exists()).toBe(false)
    w.unmount()
  })

  it('survives an undo when a mode has a preference row', async () => {
    // Mode 2 of editableProfile carries `mouse_speed = 150` as a preference row (C7).
    const { w, docStore, errors } = await page()

    docStore.setInputName('lip', 'Chin')
    await settle()
    expect(docStore.dirty).toBe(true)

    button('Undo my changes')!.click()
    await settle()

    expect(docStore.dirty).toBe(false)
    expect(docStore.doc?.input_names.lip).toBe('Chin switch')
    // the page is still there, with every row of both modes intact
    expect(w.find('h1').text()).toBe('ddfortnite')
    expect(docStore.doc?.modes.map((m) => m.mappings.length)).toEqual([3, 2])
    expect(errors).toEqual([])

    // and the rename list still renders (it reads inputs from every row)
    button('Settings')!.click()
    await settle()
    expect(document.body.querySelector('#in-mp_center_sip')).not.toBeNull()
    w.unmount()
  })

  describe('export', () => {
    const errorsFound = validation({
      errors: 1,
      findings: [{ severity: 'error', mode: 1, row: 4, message: "Unknown output 'nope'" }],
      consequence: { error: 'The QuadStick will not read this profile correctly.' },
    })

    it('trusts the check that follows the save, not the stale one the button showed', async () => {
      // clean on load; the check after the save finds an error
      let checks = 0
      const { w, docStore, fetchMock } = await page({
        'PUT /api/profiles/1': editableProfile(),
        'POST /api/profiles/validate': () => (++checks === 1 ? validation({ budget: budget() }) : errorsFound),
      })
      docStore.setInputName('lip', 'Chin')
      await settle()
      const exportButton = button('Export CSV')!
      expect(exportButton.disabled).toBe(false) // the live check has not run yet
      exportButton.click()
      await settle(12)
      expect(fetchMock.mock.calls.some((c) => c[1]?.method === 'PUT')).toBe(true)
      expect(fetchMock.mock.calls.some((c) => String(c[0]).includes('export.csv'))).toBe(false)
      expect(document.body.textContent).toContain('Export refused')
      expect(document.body.textContent).toContain("Unknown output 'nope'")
      w.unmount()
    })

    it('shows a row-anchored error from the live check as a finding, not as a failed request', async () => {
      // R1: an imported file with `x,repeat five 2000,lip,` used to come back from
      // POST /profiles/validate as a 422, and the editor showed "request failed".
      // The API now answers 200 with the row error; the editor must show that row.
      const badParam = validation({
        errors: 1,
        findings: [
          { severity: 'error', mode: 1, row: 4, message: "Function parameter 'five' is not a whole number" },
        ],
        consequence: { error: 'The QuadStick will not read this profile correctly.' },
        budget: budget({ modes_used: 2 }),
      })
      const { w, docStore, errors } = await page({ 'POST /api/profiles/validate': badParam })
      const text = document.body.textContent ?? ''
      expect(text).toContain("Function parameter 'five' is not a whole number")
      expect(text).toMatch(/Mode 1\s*·\s*row 4/)
      expect(text).toContain('The QuadStick will not read this profile correctly.')
      // it is a finding, not a connection or shape error
      expect(w.find('[role="alert"]').exists()).toBe(false)
      expect(docStore.error).toBeNull()
      expect(docStore.validation?.errors).toBe(1)
      expect(errors).toEqual([])
      // and export is refused up front rather than after a round trip
      expect(button('Export CSV')!.disabled).toBe(true)
      w.unmount()
    })

    it("shows the API's findings when it refuses the export", async () => {
      const { w } = await page({
        '/api/profiles/1/export.csv': conflict('Export refused: fix the validation errors first', errorsFound),
      })
      button('Export CSV')!.click()
      await settle()
      expect(document.body.textContent).toContain('Export refused')
      expect(document.body.textContent).toContain("Unknown output 'nope'")
      expect(document.body.textContent).toContain('Mode 1, row 4')
      // it is a refusal with reasons, not a connection error
      expect(w.find('[role="alert"]').exists()).toBe(false)
      w.unmount()
    })
  })

  describe('profile settings', () => {
    function select(id: string) {
      return document.body.querySelector<HTMLSelectElement>(id)!
    }
    async function choose(sel: HTMLSelectElement, value: string) {
      sel.value = value
      sel.dispatchEvent(new Event('change'))
      await settle()
    }

    it('writes the emulation mode into the enable_DS3_emulation preference row', async () => {
      const { w, docStore } = await page()
      button('Settings')!.click()
      await settle()
      expect(select('#p-emu').value).toBe('') // editableProfile carries no such row

      await choose(select('#p-emu'), '6')
      expect(docStore.doc?.preferences.enable_DS3_emulation).toBe('6')
      // 6 hides the drive on 2373 in the test catalog, and the warning reads the row
      expect(document.body.textContent).toContain('hides the flash drive')

      await choose(select('#p-emu'), '4')
      expect(docStore.doc?.preferences.enable_DS3_emulation).toBe('4')
      expect(document.body.textContent).toContain('stays visible on firmware 2373. Good.')

      // "not set" deletes the row rather than writing an empty value
      await choose(select('#p-emu'), '')
      expect(docStore.doc?.preferences).not.toHaveProperty('enable_DS3_emulation')
      w.unmount()
    })

    it('shows a row value the catalog does not list instead of a blank select', async () => {
      const { w } = await page({
        '/api/profiles/1': editableProfile({ preferences: { enable_DS3_emulation: '9' } }),
      })
      button('Settings')!.click()
      await settle()
      expect(select('#p-emu').value).toBe('9')
      expect(select('#p-emu').selectedOptions[0]?.textContent).toContain('(current) 9')
      w.unmount()
    })

    it('cannot say whether the drive stays visible on a firmware the catalog does not know', async () => {
      const { w } = await page({
        '/api/profiles/1': editableProfile({ firmware: 9999, preferences: { enable_DS3_emulation: '4' } }),
      })
      button('Settings')!.click()
      await settle()
      const text = document.body.textContent ?? ''
      expect(text).toMatch(/cannot tell\s+whether the flash drive stays visible/i)
      expect(text).not.toContain('Good.')
      w.unmount()
    })

    it('sets every mode from Connected by, and says when they differ', async () => {
      const p = editableProfile()
      p.modes[1]!.channel = 'bluetooth'
      const { w, docStore } = await page({ '/api/profiles/1': p })
      button('Settings')!.click()
      await settle()
      expect(select('#p-channel').value).toBe('mixed')

      await choose(select('#p-channel'), 'both')
      expect(docStore.doc?.modes.map((m) => m.channel)).toEqual(['both', 'both'])
      expect(select('#p-channel').value).toBe('both')
      // and the profile body no longer carries a channel of its own
      expect(docStore.doc).not.toHaveProperty('channel')
      w.unmount()
    })
  })

  describe('unsaved changes', () => {
    it('asks before opening another profile, and stays put when refused', async () => {
      const { w, router, docStore, fetchMock } = await page({
        '/api/profiles/2': editableProfile({ id: 2, name: 'Other' }),
      })
      const confirm = vi.fn(() => false)
      vi.stubGlobal('confirm', confirm)
      docStore.setInputName('lip', 'Chin')
      await settle()

      await router.push('/profiles/2')
      await settle()
      expect(confirm).toHaveBeenCalledTimes(1)
      expect(router.currentRoute.value.path).toBe('/profiles/1')
      expect(docStore.doc?.input_names.lip).toBe('Chin') // the edit survived
      expect(fetchMock.mock.calls.some((c) => String(c[0]).endsWith('/api/profiles/2'))).toBe(false)

      // agreed this time: the other profile loads
      confirm.mockReturnValue(true)
      await router.push('/profiles/2')
      await settle()
      expect(router.currentRoute.value.path).toBe('/profiles/2')
      expect(w.find('h1').text()).toBe('Other')
      w.unmount()
    })

    it('does not ask when nothing changed', async () => {
      const { w, router } = await page({
        '/api/profiles/2': editableProfile({ id: 2, name: 'Other' }),
      })
      const confirm = vi.fn(() => false)
      vi.stubGlobal('confirm', confirm)
      await router.push('/profiles/2')
      await settle()
      expect(confirm).not.toHaveBeenCalled()
      expect(w.find('h1').text()).toBe('Other')
      w.unmount()
    })

    it('asks before leaving the editor altogether', async () => {
      const { w, router, docStore } = await page()
      const confirm = vi.fn(() => false)
      vi.stubGlobal('confirm', confirm)
      docStore.setInputName('lip', 'Chin')
      await settle()
      await router.push('/')
      await settle()
      expect(confirm).toHaveBeenCalledTimes(1)
      expect(router.currentRoute.value.path).toBe('/profiles/1')
      w.unmount()
    })
  })
})
