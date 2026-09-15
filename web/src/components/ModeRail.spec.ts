import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ModeRail from './ModeRail.vue'
import { useCatalogStore } from '@/stores/catalog'
import { useDocumentStore } from '@/stores/document'
import { budget, catalog, editableProfile, stubFetch, validation } from '@/test/factories'

async function setup(profileOver = {}) {
  vi.stubGlobal(
    'fetch',
    stubFetch({
      '/api/catalog': catalog(),
      '/api/profiles/1': editableProfile(profileOver),
      'POST /api/profiles/validate': validation({
        budget: budget({
          modes_used: 2,
          modes: [
            { number: 1, name: 'Left', rows_used: 3, rows_free: 125, rows_active: 3, unused_inputs: [] },
            { number: 2, name: 'Right', rows_used: 2, rows_free: 126, rows_active: 1, unused_inputs: [] },
          ],
        }),
      }),
    }),
  )
  const cat = useCatalogStore()
  await cat.load()
  const docStore = useDocumentStore()
  await docStore.load(1)
  const w = mount(ModeRail)
  return { w, docStore }
}

describe('ModeRail', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.unstubAllGlobals()
  })

  it('numbers modes by position and shows how many rows each uses', async () => {
    const { w } = await setup()
    const items = w.findAll('li')
    expect(items).toHaveLength(2)
    expect(items[0]!.text()).toContain('1')
    expect(items[0]!.text()).toContain('Left')
    expect(items[0]!.text()).toContain('3 rows')
  })

  // "Left Analog" was being cut to "Left Anal…" by the five LED dots sharing its
  // line. A mode name is how you tell modes apart, so it gets the full width and
  // the dots hang below it.
  it('shows a long mode name in full, with the lights below it', async () => {
    const { w, docStore } = await setup()
    docStore.renameMode(docStore.doc!.modes[0]!.key, 'Mouse Scroll Analog')
    await w.vm.$nextTick()
    const name = w.findAll('li')[0]!.find('.names b')
    expect(name.text()).toBe('Mouse Scroll Analog')
    // the dots are in the row under the name, not beside it
    expect(w.findAll('li')[0]!.findAll('.names .under .leds i')).toHaveLength(5)
  })

  it('reorders with buttons rather than dragging, and renumbers', async () => {
    const { w, docStore } = await setup()
    // no draggable anywhere: dragging needs a held pointer, which this app forbids
    expect(w.find('[draggable="true"]').exists()).toBe(false)
    const down = w.findAll('li')[0]!.findAll('button').find((b) => b.text() === '↓')!
    await down.trigger('click')
    expect(docStore.doc!.modes.map((m) => m.name)).toEqual(['Right', 'Left'])
    expect(w.findAll('li')[0]!.text()).toContain('Right')
  })

  it('disables the move that would fall off the end', async () => {
    const { w } = await setup()
    const firstUp = w.findAll('li')[0]!.findAll('button').find((b) => b.text() === '↑')!
    const lastDown = w.findAll('li')[1]!.findAll('button').find((b) => b.text() === '↓')!
    expect(firstUp.attributes('disabled')).toBeDefined()
    expect(lastDown.attributes('disabled')).toBeDefined()
  })

  it('selects a mode when clicked', async () => {
    const { w, docStore } = await setup()
    await w.findAll('li')[1]!.find('.pick').trigger('click')
    expect(docStore.selectedMode?.name).toBe('Right')
  })

  it('shows the LED pattern for each mode, in the firmware colours', async () => {
    const { w, docStore } = await setup()
    const lit = (i: number) =>
      w.findAll('li')[i]!.findAll('.leds i').map((n) => n.classes().includes('on'))
    const colours = (i: number) =>
      w.findAll('li')[i]!.findAll('.leds i').map((n) =>
        ['purple', 'blue', 'red'].find((c) => n.classes().includes(c)) ?? 'off',
      )
    // mode 1 lights LED 1 only; mode 2 lights LED 2 only, both purple
    expect(lit(0)).toEqual([true, false, false, false, false])
    expect(lit(1)).toEqual([false, true, false, false, false])
    expect(colours(0)).toEqual(['purple', 'off', 'off', 'off', 'off'])

    // grow to 16: LED 5 goes blue for 10–14 and red for 15–16, as the device does
    for (let i = 3; i <= 16; i++) docStore.addMode(`M${i}`, 16)
    await w.vm.$nextTick()
    expect(colours(9)).toEqual(['off', 'off', 'off', 'off', 'blue']) // mode 10
    expect(colours(11)).toEqual(['off', 'purple', 'off', 'off', 'blue']) // mode 12
    expect(colours(14)).toEqual(['off', 'off', 'off', 'off', 'red']) // mode 15
    expect(colours(15)).toEqual(['purple', 'off', 'off', 'off', 'red']) // mode 16
  })

  it('adds a mode and stops at the firmware limit', async () => {
    const { w, docStore } = await setup()
    const add = w.findAll('button').find((b) => b.text() === 'Add')!
    await w.find('#new-mode').setValue('Driving')
    await add.trigger('click')
    expect(docStore.doc!.modes.map((m) => m.name)).toContain('Driving')

    for (let i = 0; i < 20; i++) docStore.addMode(`M${i}`, 16)
    await w.vm.$nextTick()
    expect(docStore.doc!.modes).toHaveLength(16)
    expect(w.text()).toContain('16 of 16 modes')
    expect(w.find('#new-mode').attributes('disabled')).toBeDefined()
  })

  it('does not warn of a clash between modes 5 and 10: colour tells them apart', async () => {
    const { w, docStore } = await setup()
    // grow to 16 modes: every pattern is distinct once LED 5's colour counts, so the
    // "look the same" warning stays unreachable for the firmware's own table
    for (let i = 3; i <= 16; i++) docStore.addMode(`M${i}`, 16)
    await w.vm.$nextTick()
    expect(w.text()).not.toContain('look the same as mode')
    expect(w.findAll('.clash')).toHaveLength(0)
  })

  it('flags which mode holds the problems', async () => {
    const { w, docStore } = await setup()
    docStore.validation = validation({
      errors: 1,
      warnings: 1,
      findings: [
        { severity: 'error', mode: 1, row: 4, message: 'bad' },
        { severity: 'warning', mode: 2, row: null, message: 'meh' },
      ],
    })
    await w.vm.$nextTick()
    expect(w.findAll('li')[0]!.find('.badge--error').text()).toBe('1')
    expect(w.findAll('li')[1]!.find('.badge--warning').text()).toBe('1')
  })

  it('renames a mode, and the label and its game actions follow', async () => {
    const { w, docStore } = await setup({
      game_actions: [
        { id: 1, output: 'x', action: 'Jump', mode_name: null },
        { id: 2, output: 'circle', action: 'Fire', mode_name: 'Left' },
      ],
    })
    await w.findAll('li')[0]!.findAll('button').find((b) => b.text() === 'Rename')!.trigger('click')
    const box = w.find('input[aria-label="Rename mode 1"]')
    // its own control, not a child of the select button: Enter must not bubble
    // into a button, and every browser must be able to focus it with a mouse
    expect(box.element.closest('button')).toBeNull()
    await box.setValue('Driving')
    await box.trigger('keydown', { key: 'Enter' })
    expect(w.find('input[aria-label="Rename mode 1"]').exists()).toBe(false)

    const mode = docStore.doc!.modes[0]!
    expect(mode.name).toBe('Driving')
    // the device shows one cell for both, so they never differ
    expect(mode.label).toBe('Driving')
    // the card's per-mode labels are keyed by mode name, so they move with it
    expect(docStore.actionFor('circle', 'Driving')).toBe('Fire')
    expect(docStore.doc!.game_actions.find((g) => g.output === 'circle')!.mode_name).toBe('Driving')
    // the profile-wide one is untouched
    expect(docStore.doc!.game_actions.find((g) => g.output === 'x')!.mode_name).toBeNull()
  })

  it('cancels a rename with Escape, leaving the name alone', async () => {
    const { w, docStore } = await setup()
    await w.findAll('li')[0]!.findAll('button').find((b) => b.text() === 'Rename')!.trigger('click')
    const box = w.find('input[aria-label="Rename mode 1"]')
    await box.setValue('Nope')
    await box.trigger('keydown', { key: 'Escape' })
    expect(docStore.doc!.modes[0]!.name).toBe('Left')
    expect(w.find('input[aria-label="Rename mode 1"]').exists()).toBe(false)
  })

  it('asks before deleting a mode, and deletes only on the confirm', async () => {
    const { w, docStore } = await setup()
    await w.findAll('li')[0]!.findAll('button').find((b) => b.text() === 'Delete')!.trigger('click')
    await w.vm.$nextTick()
    // nothing gone yet; the question is on screen, with the mode named
    expect(docStore.doc!.modes).toHaveLength(2)
    const dialog = document.body.querySelector('[role="dialog"]')!
    expect(dialog).not.toBeNull()
    expect(dialog.textContent).toContain('Left')
    expect(dialog.textContent).toContain('3 rows')

    const confirm = [...dialog.querySelectorAll('footer button')].find(
      (b) => (b.textContent ?? '').trim() === 'Delete',
    ) as HTMLButtonElement
    confirm.click()
    await w.vm.$nextTick()
    expect(docStore.doc!.modes.map((m) => m.name)).toEqual(['Right'])
    expect(document.body.querySelector('[role="dialog"]')).toBeNull()
  })

  it('keeps the mode when the delete is called off', async () => {
    const { w, docStore } = await setup()
    await w.findAll('li')[0]!.findAll('button').find((b) => b.text() === 'Delete')!.trigger('click')
    await w.vm.$nextTick()
    const keep = [...document.body.querySelectorAll('[role="dialog"] footer button')].find(
      (b) => (b.textContent ?? '').trim() === 'Keep it',
    ) as HTMLButtonElement
    keep.click()
    await w.vm.$nextTick()
    expect(docStore.doc!.modes).toHaveLength(2)
    expect(document.body.querySelector('[role="dialog"]')).toBeNull()
  })

  it('names its move buttons for a screen reader', async () => {
    const { w } = await setup()
    const up = w.findAll('li')[1]!.findAll('button').find((b) => b.text() === '↑')!
    expect(up.attributes('aria-label')).toContain('Move Right up')
  })
})
