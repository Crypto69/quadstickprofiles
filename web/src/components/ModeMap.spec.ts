import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ModeMap from './ModeMap.vue'
import { useCatalogStore } from '@/stores/catalog'
import { useDocumentStore } from '@/stores/document'
import { budget, catalog, editableProfile, stubFetch, validation } from '@/test/factories'

async function setup(profileOver = {}) {
  vi.stubGlobal(
    'fetch',
    stubFetch({
      '/api/catalog': catalog(),
      '/api/profiles/1': editableProfile(profileOver),
      'POST /api/profiles/validate': validation({ budget: budget() }),
    }),
  )
  await useCatalogStore().load()
  const docStore = useDocumentStore()
  await docStore.load(1)
  return { w: mount(ModeMap), docStore }
}

describe('ModeMap', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.unstubAllGlobals()
  })

  it('draws one node per mode', async () => {
    const { w } = await setup()
    expect(w.findAll('circle.node')).toHaveLength(2)
    expect(w.text()).toContain('Left')
    expect(w.text()).toContain('Right')
  })

  it('draws an arrow for each mode change, and names the input', async () => {
    const { w } = await setup()
    // mode 1 increments on right_sip, mode 2 decrements on right_puff
    expect(w.findAll('path.edge').length).toBe(2)
    const edges = w.findAll('.edges li').map((l) => l.text())
    expect(edges.some((e) => e.includes('1 → 2') && e.includes('Side tube sip'))).toBe(true)
    expect(edges.some((e) => e.includes('2 → 1') && e.includes('Side tube puff'))).toBe(true)
  })

  it('says so when every mode has a way out', async () => {
    const { w } = await setup()
    expect(w.text()).toContain('Every mode has a way out')
    expect(w.findAll('g.trapped')).toHaveLength(0)
  })

  it('marks a mode you cannot leave, and explains the consequence', async () => {
    const { w, docStore } = await setup()
    // strip the mode change out of mode 2
    const mode2 = docStore.doc!.modes[1]!
    mode2.mappings = mode2.mappings.filter((m) => m.output !== 'decrement_mode')
    await w.vm.$nextTick()
    expect(w.findAll('g.trapped')).toHaveLength(1)
    const warning = w.find('.trap-warning').text()
    expect(warning).toContain('mode 2 (Right)')
    expect(warning).toContain('unplugging')
  })

  it('wraps increment past the last mode back to the first', async () => {
    const { w } = await setup()
    // mode 2 is the last, so its increment (if any) would wrap to 1; here its
    // decrement goes 2 -> 1, and mode 1's increment goes 1 -> 2
    const edges = w.findAll('.edges li').map((l) => l.text())
    expect(edges.some((e) => e.includes('2 → 1'))).toBe(true)
  })

  it('uses the profile name for the input that changes mode', async () => {
    const { w, docStore } = await setup()
    docStore.setInputName('right_sip', 'Cheek tube sip')
    await w.vm.$nextTick()
    expect(w.text()).toContain('Cheek tube sip')
  })
})
