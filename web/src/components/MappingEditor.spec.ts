import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import MappingEditor from './MappingEditor.vue'
import { useCatalogStore } from '@/stores/catalog'
import { useDocumentStore } from '@/stores/document'
import { budget, catalog, editableProfile, stubFetch, validation } from '@/test/factories'

async function setup(input: string) {
  vi.stubGlobal(
    'fetch',
    stubFetch({
      '/api/catalog': catalog(),
      '/api/profiles/1': editableProfile(),
      'POST /api/profiles/validate': validation({ budget: budget() }),
    }),
  )
  const cat = useCatalogStore()
  await cat.load()
  const docStore = useDocumentStore()
  await docStore.load(1)
  const w = mount(MappingEditor, { props: { input } })
  return { w, docStore }
}

describe('MappingEditor', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.unstubAllGlobals()
  })

  it('reads as a sentence rather than a form', async () => {
    const { w } = await setup('mp_center_sip')
    const text = w.find('.sentence').text()
    expect(text).toMatch(/^Press/)
    expect(text).toContain('when you')
    expect(text).toContain('Centre sip')
  })

  it('gives assistive tech the sentence, and keeps the select reachable', async () => {
    const { w } = await setup('mp_center_sip')
    // the readable sentence is a plain string with no option list in it
    const spoken = w.find('.sentence .sr-only')
    expect(spoken.text()).toBe('Press x when you Centre sip.')
    expect(spoken.text()).not.toContain('increment_mode')
    // the select is in the accessibility tree: nothing focusable is hidden from it
    const select = w.find('.sentence select')
    expect(select.exists()).toBe(true)
    expect(select.element.closest('[aria-hidden="true"]')).toBeNull()
    // it is described by that sentence, and named by its own label
    expect(select.attributes('aria-describedby')).toBe(spoken.attributes('id'))
    const id = select.attributes('id')
    expect(w.find(`label[for="${id}"]`).text()).toContain('Output pressed when you')
  })

  it('spells out the function in the spoken sentence when it is not plain', async () => {
    const { w, docStore } = await setup('mp_center_sip')
    const row = docStore.mappingsForInput('mp_center_sip')[0]!
    docStore.updateMapping(docStore.doc!.modes[0]!.key, row.key, {
      function: 'repeat',
      params: [5, 2000],
    })
    await w.vm.$nextTick()
    expect(w.find('.sentence .sr-only').text()).toBe('Press x when you Centre sip as repeat 5 2000.')
  })

  it('reads an empty function cell as plain, without rewriting it', async () => {
    const { w, docStore } = await setup('mp_center_sip')
    const row = docStore.mappingsForInput('mp_center_sip')[0]!
    docStore.updateMapping(docStore.doc!.modes[0]!.key, row.key, { function: '', params: [] })
    await w.vm.$nextTick()
    expect(w.find('.sentence .sr-only').text()).toBe('Press x when you Centre sip.')
    expect(docStore.mappingsForInput('mp_center_sip')[0]!.function).toBe('')
  })

  it('says plainly when an input does nothing yet', async () => {
    const { w } = await setup('mp_left_puff')
    expect(w.text()).toContain('Nothing happens when you use this yet')
  })

  it('offers only catalog outputs, never a free-text keyword', async () => {
    const { w } = await setup('mp_center_sip')
    expect(w.findAll('input[type="text"]').length).toBeLessThanOrEqual(2) // action + note only
    const select = w.find('select')
    const values = select.findAll('option').map((o) => o.attributes('value'))
    expect(values).toContain('x')
    expect(values).toContain('increment_mode')
    // the placeholder is the only non-catalog option, and it is disabled
    const placeholder = select.findAll('option').find((o) => o.attributes('value') === '')
    expect(placeholder!.attributes('disabled')).toBeDefined()
  })

  it('shows an output the catalog does not list as "(current)", rather than losing it', async () => {
    const { w, docStore } = await setup('mp_center_sip')
    const row = docStore.mappingsForInput('mp_center_sip')[0]!
    docStore.updateMapping(docStore.doc!.modes[0]!.key, row.key, { output: 'kb_a' })
    await w.vm.$nextTick()
    const select = w.find('select')
    const first = select.findAll('option').find((o) => o.attributes('disabled') === undefined)!
    expect(first.text()).toBe('(current) kb_a')
    expect(first.attributes('value')).toBe('kb_a')
    expect((select.element as HTMLSelectElement).value).toBe('kb_a')
    // and it is gone again once the value is a catalog one
    await select.setValue('circle')
    expect(w.find('select').text()).not.toContain('(current)')
  })

  it('adds a mapping to the selected mode', async () => {
    const { w, docStore } = await setup('lip')
    await w.findAll('button').find((b) => b.text().includes('Add something here'))!.trigger('click')
    expect(docStore.mappingsForInput('lip')).toHaveLength(1)
  })

  it('changes the output through the picker', async () => {
    const { w, docStore } = await setup('mp_center_sip')
    await w.find('select').setValue('circle')
    expect(docStore.mappingsForInput('mp_center_sip')[0]!.output).toBe('circle')
  })

  it('removes a mapping', async () => {
    const { w, docStore } = await setup('mp_center_sip')
    await w.findAll('button').find((b) => b.text() === 'Remove')!.trigger('click')
    expect(docStore.mappingsForInput('mp_center_sip')).toHaveLength(0)
  })

  it('shows a sequence row read-only, and explains why', async () => {
    // the sequence fires on its last input, mp_right_sip
    const { w } = await setup('mp_right_sip')
    const text = w.text()
    expect(text).toContain('in that order')
    expect(text).toContain('not verified on a device')
    expect(w.find('select').exists()).toBe(false) // nothing editable
    expect(w.findAll('button').some((b) => b.text() === 'Remove')).toBe(false)
  })

  it('sets a game action, which is what the card prints', async () => {
    const { w, docStore } = await setup('mp_center_sip')
    await w.findAll('button').find((b) => b.text() === 'Details')!.trigger('click')
    const action = w.find('input[type="text"]')
    await action.setValue('Fire')
    expect(docStore.actionFor('x', 'Left')).toBe('Fire')
  })

  it('marks an older input name as such', async () => {
    const { w } = await setup('push')
    expect(w.find('.badge--warning').text()).toContain('older name')
  })
})
