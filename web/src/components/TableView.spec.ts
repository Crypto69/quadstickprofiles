import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import TableView from './TableView.vue'
import { useCatalogStore } from '@/stores/catalog'
import { useDocumentStore } from '@/stores/document'
import { budget, catalog, editableProfile, stubFetch, validation } from '@/test/factories'

async function setup() {
  vi.stubGlobal(
    'fetch',
    stubFetch({
      '/api/catalog': catalog(),
      '/api/profiles/1': editableProfile(),
      'POST /api/profiles/validate': validation({ budget: budget() }),
    }),
  )
  await useCatalogStore().load()
  const docStore = useDocumentStore()
  await docStore.load(1)
  const w = mount(TableView)
  return { w, docStore }
}

describe('TableView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.unstubAllGlobals()
  })

  it('numbers rows the way the spreadsheet does, starting at 4', async () => {
    const { w } = await setup()
    const nums = w.findAll('tbody .rownum').map((n) => n.text())
    expect(nums).toEqual(['4', '5', '6'])
  })

  it('never offers a free-text keyword cell', async () => {
    const { w } = await setup()
    // the only text inputs are the notes column; outputs and inputs are selects
    const textInputs = w.findAll('input[type="text"]')
    const notes = w.findAll('input[aria-label^="Note on row"]')
    expect(textInputs.length).toBe(notes.length)
    expect(w.findAll('select[aria-label^="Output on row"]').length).toBeGreaterThan(0)
    expect(w.findAll('select[aria-label^="Input on row"]').length).toBeGreaterThan(0)
  })

  it('lets a row have no input, which is how an unused row is written', async () => {
    const { w, docStore } = await setup()
    const inputSelect = w.find('select[aria-label="Input on row 4"]')
    expect(inputSelect.findAll('option').some((o) => o.attributes('value') === '')).toBe(true)
    await inputSelect.setValue('')
    expect(docStore.doc!.modes[0]!.mappings[0]!.inputs).toEqual([])
  })

  it('locks a sequence row and says why', async () => {
    const { w } = await setup()
    const locked = w.findAll('tbody tr').filter((r) => r.classes().includes('locked'))
    expect(locked).toHaveLength(1) // the two-input row
    expect(locked[0]!.text()).toContain('A sequence')
    expect(locked[0]!.find('select').exists()).toBe(false)
  })

  it('locks a preference override row and shows what it sets', async () => {
    const { w, docStore } = await setup()
    docStore.selectMode(docStore.doc!.modes[1]!.key)
    await w.vm.$nextTick()
    const locked = w.findAll('tbody tr').filter((r) => r.classes().includes('locked'))
    expect(locked).toHaveLength(1)
    expect(locked[0]!.text()).toContain('mouse_speed')
    expect(locked[0]!.text()).toContain('150')
    expect(locked[0]!.text()).toContain('while this mode is active')
  })

  it('edits an output through a constrained list', async () => {
    const { w, docStore } = await setup()
    await w.find('select[aria-label="Output on row 4"]').setValue('circle')
    expect(docStore.doc!.modes[0]!.mappings[0]!.output).toBe('circle')
  })

  it('shows Xbox names when the profile uses them', async () => {
    const { w, docStore } = await setup()
    docStore.doc!.console = 'xbox'
    await w.vm.$nextTick()
    const options = w.find('select[aria-label="Output on row 4"]').findAll('option').map((o) => o.text())
    expect(options).toContain('A') // x under Xbox naming
    expect(options).not.toContain('x')
  })

  it('lists problems against the row they are on', async () => {
    const { w, docStore } = await setup()
    docStore.validation = validation({
      errors: 1,
      findings: [
        { severity: 'error', mode: 1, row: 5, message: 'this row is wrong' },
        { severity: 'warning', mode: 1, row: null, message: 'mode-level, belongs elsewhere' },
      ],
    })
    await w.vm.$nextTick()
    const problems = w.findAll('.row-problems li').map((l) => l.text())
    expect(problems).toHaveLength(1)
    expect(problems[0]).toContain('Row 5')
    expect(problems[0]).toContain('this row is wrong')
  })

  it('adds and deletes rows', async () => {
    const { w, docStore } = await setup()
    await w.findAll('button').find((b) => b.text() === 'Add a row')!.trigger('click')
    expect(docStore.doc!.modes[0]!.mappings).toHaveLength(4)
    await w.find('button[aria-label="Delete row 4"]').trigger('click')
    expect(docStore.doc!.modes[0]!.mappings).toHaveLength(3)
  })

  it('offers to hide the rows nothing triggers, and counts them', async () => {
    const { w, docStore } = await setup()
    // the fixture mode has three rows, all with inputs
    expect(w.find('.check').text()).toContain('Hide the 0 rows')
    expect(w.find('.check input').attributes('disabled')).toBeDefined()

    // add two rows with no input, as a real profile is full of
    docStore.addMapping(docStore.doc!.modes[0]!.key, { output: 'dpad_N' })
    docStore.addMapping(docStore.doc!.modes[0]!.key, { output: 'dpad_E' })
    await w.vm.$nextTick()
    expect(w.find('.check').text()).toContain('Hide the 2 rows')
    expect(w.find('.check input').attributes('disabled')).toBeUndefined()
    expect(w.findAll('tbody tr')).toHaveLength(5)

    await w.find('.check input').setValue(true)
    expect(w.findAll('tbody tr')).toHaveLength(3)
    expect(w.text()).toContain('Showing 3 of 5')
  })

  it('keeps the spreadsheet row numbers when rows are hidden', async () => {
    const { w, docStore } = await setup()
    const key = docStore.doc!.modes[0]!.key
    // an unused row in the middle, so hiding it would renumber if we got this wrong
    docStore.updateMapping(key, docStore.doc!.modes[0]!.mappings[1]!.key, { inputs: [] })
    await w.vm.$nextTick()
    expect(w.findAll('tbody .rownum').map((n) => n.text())).toEqual(['4', '5', '6'])

    await w.find('.check input').setValue(true)
    // row 5 is gone, and 4 and 6 keep their own numbers — they are the file's rows
    expect(w.findAll('tbody .rownum').map((n) => n.text())).toEqual(['4', '6'])
  })

  it('does not hide a sequence or a preference row, which are not unused', async () => {
    const { w, docStore } = await setup()
    await w.find('.check input').setValue(true)
    // the sequence row has two inputs, so it stays
    expect(w.findAll('tbody tr')).toHaveLength(3)

    docStore.selectMode(docStore.doc!.modes[1]!.key)
    await w.vm.$nextTick()
    // mode 2 is a preference override plus one mapping; neither is unused
    expect(w.findAll('tbody tr')).toHaveLength(2)
    expect(w.text()).toContain('mouse_speed')
  })

  it('still lists a problem that sits on a hidden row', async () => {
    const { w, docStore } = await setup()
    docStore.updateMapping(
      docStore.doc!.modes[0]!.key,
      docStore.doc!.modes[0]!.mappings[1]!.key,
      { inputs: [] },
    )
    docStore.validation = validation({
      warnings: 1,
      findings: [{ severity: 'warning', mode: 1, row: 5, message: 'something about row 5' }],
    })
    await w.vm.$nextTick()
    await w.find('.check input').setValue(true)
    // row 5 is hidden, but its problem must not vanish without explanation
    expect(w.findAll('tbody .rownum').map((n) => n.text())).not.toContain('5')
    expect(w.find('.row-problems').text()).toContain('something about row 5')
  })

  it('explains an empty table rather than showing nothing', async () => {
    const { w, docStore } = await setup()
    const mode = docStore.doc!.modes[0]!
    for (const m of mode.mappings) docStore.updateMapping(mode.key, m.key, { inputs: [] })
    // the sequence row is now input-less too, so every row is unused
    await w.vm.$nextTick()
    await w.find('.check input').setValue(true)
    expect(w.findAll('tbody tr')).toHaveLength(0)
    expect(w.text()).toContain('Every row in this mode is waiting for an input')
  })

  it('edits the function through the picker, never as free text', async () => {
    const { w, docStore } = await setup()
    const cell = w.find('button[aria-label^="How row 4 behaves"]')
    expect(cell.text()).toBe('normal')
    expect(cell.attributes('aria-expanded')).toBe('false')
    expect(w.find('tr.details').exists()).toBe(false)

    await cell.trigger('click')
    expect(w.find('tr.details').exists()).toBe(true)
    await w.find('tr.details select').setValue('repeat')
    expect(docStore.doc!.modes[0]!.mappings[0]!.function).toBe('repeat')
    expect(docStore.doc!.modes[0]!.mappings[0]!.params).toEqual([]) // picked bare

    await w.find('tr.details input[type="number"]').setValue('7')
    expect(docStore.doc!.modes[0]!.mappings[0]!.params).toEqual([7])
    expect(w.find('button[aria-label^="How row 4 behaves"]').text()).toBe('repeat 7')

    // still no free-text keyword anywhere
    const textInputs = w.findAll('input[type="text"]')
    expect(textInputs.length).toBe(w.findAll('input[aria-label^="Note on row"]').length)

    await w.findAll('button').find((b) => b.text() === 'Done')!.trigger('click')
    expect(w.find('tr.details').exists()).toBe(false)
  })

  it('does not open the picker on a locked row', async () => {
    const { w } = await setup()
    const locked = w.findAll('tbody tr').filter((r) => r.classes().includes('locked'))[0]!
    expect(locked.find('button[aria-label^="How row"]').exists()).toBe(false)
  })

  it('shows a value the catalog does not list as "(current)", rather than losing it', async () => {
    const { w, docStore } = await setup()
    const mode = docStore.doc!.modes[0]!
    docStore.updateMapping(mode.key, mode.mappings[0]!.key, { output: 'kb_a', inputs: ['push'] })
    await w.vm.$nextTick()

    const out = w.find('select[aria-label="Output on row 4"]')
    const first = out.findAll('option').find((o) => o.attributes('disabled') === undefined)!
    expect(first.text()).toBe('(current) kb_a')
    expect(first.attributes('value')).toBe('kb_a')
    expect((out.element as HTMLSelectElement).value).toBe('kb_a')

    const inp = w.find('select[aria-label="Input on row 4"]')
    const cur = inp.findAll('option').find((o) => o.text().startsWith('(current)'))!
    expect(cur.text()).toBe('(current) push')
    expect((inp.element as HTMLSelectElement).value).toBe('push')

    // a known value gets no such option
    docStore.updateMapping(mode.key, mode.mappings[0]!.key, { output: 'x', inputs: ['mp_center_sip'] })
    await w.vm.$nextTick()
    expect(w.find('select[aria-label="Output on row 4"]').text()).not.toContain('(current)')
    expect(w.find('select[aria-label="Input on row 4"]').text()).not.toContain('(current)')
  })

  it('says notes never reach the device', async () => {
    const { w } = await setup()
    expect(w.text()).toContain('The QuadStick never sees them')
  })
})
