import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import PreferencesEditor from './PreferencesEditor.vue'
import { useCatalogStore } from '@/stores/catalog'
import { catalog, stubFetch } from '@/test/factories'

async function editor(values: Record<string, string> = {}, extra = {}) {
  vi.stubGlobal('fetch', stubFetch({ '/api/catalog': catalog() }))
  await useCatalogStore().load()
  return mount(PreferencesEditor, { props: { values, ...extra } })
}

describe('PreferencesEditor', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.unstubAllGlobals()
  })

  it('groups settings by what they affect', async () => {
    const w = await editor()
    const headings = w.findAll('summary').map((s) => s.text())
    expect(headings.some((h) => h.startsWith('Mouse'))).toBe(true)
    expect(headings.some((h) => h.startsWith('Sound and lights'))).toBe(true)
  })

  it('hides the fiddly ones until asked', async () => {
    const w = await editor()
    expect(w.text()).not.toContain('Circular dead zone')
    expect(w.text()).toContain('Show the fiddly ones')
    await w.find('.check input').setValue(true)
    expect(w.text()).toContain('Circular dead zone')
  })

  it('still shows a fiddly one that is actually set', async () => {
    const w = await editor({ joystick_dead_zone_shape: '0' })
    expect(w.text()).toContain('Circular dead zone')
  })

  it('counts what is set, here and per group', async () => {
    const w = await editor({ volume: '40', mouse_speed: '150' })
    expect(w.text()).toContain('2 settings are set here')
    const mouse = w.findAll('summary').find((s) => s.text().startsWith('Mouse'))!
    expect(mouse.text()).toContain('1 of 2 set')
  })

  it('says what happens to a blank one', async () => {
    const w = await editor({}, { inheritedFrom: 'the QuadStick' })
    expect(w.text()).toContain('decided by')
    expect(w.text()).toContain('the QuadStick')
  })

  it('searches by label, keyword and description', async () => {
    const w = await editor()
    await w.find('#pref-search').setValue('pointer') // only in the description
    expect(w.text()).toContain('Mouse speed')
    expect(w.text()).not.toContain('Speaker volume')

    await w.find('#pref-search').setValue('volume')
    expect(w.text()).toContain('Speaker volume')

    await w.find('#pref-search').setValue('zzzz')
    expect(w.text()).toContain('Nothing matches')
  })

  it('passes an edit up with the key', async () => {
    const w = await editor({ volume: '40' })
    const input = w.find('#pref-volume')
    await input.setValue('55')
    expect(w.emitted('update')!.at(-1)).toEqual(['volume', '55'])
  })

  it('shows the inherited value in a blank field', async () => {
    const w = await editor({}, { inheritedFrom: 'the device', inherited: { volume: '77' } })
    expect(w.find('#pref-volume').attributes('placeholder')).toBe('77')
  })

  it('can be narrowed to a named set of keys', async () => {
    const w = await editor({}, { only: ['volume'] })
    expect(w.text()).toContain('Speaker volume')
    expect(w.text()).not.toContain('Mouse speed')
  })
})
