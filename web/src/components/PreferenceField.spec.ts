import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import PreferenceField from './PreferenceField.vue'
import type { PreferenceEntry } from '@/api/types'

const INT: PreferenceEntry = {
  label: 'Mouse speed', category: 'Mouse', editor: 'integer', default: '100',
  minimum: 10, maximum: 200, unit: 'percent',
  description: 'How fast the pointer moves.',
}
const TOGGLE: PreferenceEntry = {
  label: 'Circular dead zone', category: 'Joystick', editor: 'toggle', default: '1',
}
const CHOICE: PreferenceEntry = {
  label: 'Mouse response curve', category: 'Mouse', editor: 'choice', default: '1',
  options: ['0', '1', '2'],
  optionLabels: { '0': 'Linear', '1': 'Parabolic', '2': 'Steeper parabolic' },
}
const TEXT: PreferenceEntry = {
  label: 'Bluetooth address', category: 'Bluetooth', editor: 'text', default: '',
}

function field(entry: PreferenceEntry, value: string | undefined, extra = {}) {
  return mount(PreferenceField, {
    props: { name: 'a_key', entry, value, ...extra },
  })
}

describe('PreferenceField', () => {
  it('gives a number its range and unit, and tells the browser too', () => {
    const w = field(INT, '120')
    const input = w.find('input[type="number"]')
    expect(input.attributes('min')).toBe('10')
    expect(input.attributes('max')).toBe('200')
    expect(w.text()).toContain('10 to 200 percent')
    expect(w.text()).toContain('normally 100')
  })

  it('renders a toggle as a checkbox mapped to 0 and 1', async () => {
    const box = (w: ReturnType<typeof field>) =>
      w.find<HTMLInputElement>('input[type="checkbox"]').element.checked

    const off = field(TOGGLE, '0')
    expect(box(off)).toBe(false)
    expect(off.text()).toContain('Off')

    const on = field(TOGGLE, '1')
    expect(box(on)).toBe(true)
    expect(on.text()).toContain('On')

    await off.find('input[type="checkbox"]').setValue(true)
    expect(off.emitted('update')!.at(-1)).toEqual(['1'])
  })

  it('names each choice where the manual names it', () => {
    const w = field(CHOICE, '1')
    const labels = w.findAll('option').map((o) => o.text())
    expect(labels.some((l) => l.includes('Parabolic'))).toBe(true)
    expect(labels.some((l) => l.includes('Linear'))).toBe(true)
    // and the values are still the firmware's
    const values = w.findAll('option').map((o) => o.attributes('value'))
    expect(values).toContain('0')
    expect(values).toContain('2')
  })

  it('offers plain text where the setting is free-form', () => {
    const w = field(TEXT, '')
    expect(w.find('input[type="text"]').exists()).toBe(true)
    expect(w.find('input[type="number"]').exists()).toBe(false)
  })

  it('treats blank as "not set here", which is not the same as the default', () => {
    const unset = field(INT, undefined, {
      inheritedFrom: "the QuadStick's own settings",
      inheritedValue: '80',
    })
    expect(unset.classes()).not.toContain('set')
    expect(unset.text()).toContain('Not set here')
    expect(unset.text()).toContain("the QuadStick's own settings")
    // the placeholder shows what will actually apply, not the catalog default
    expect(unset.find('input').attributes('placeholder')).toBe('80')
    expect(unset.findAll('button')).toHaveLength(0) // nothing to unset

    const set = field(INT, '120', { inheritedFrom: 'the device', inheritedValue: '80' })
    expect(set.classes()).toContain('set')
    expect(set.text()).not.toContain('Not set here')
  })

  it('falls back to the catalog default when nothing is inherited', () => {
    const w = field(INT, undefined)
    expect(w.find('input').attributes('placeholder')).toBe('100')
  })

  it('can be unset again, emitting empty rather than a zero', async () => {
    const w = field(INT, '120')
    const btn = w.findAll('button').find((b) => b.text() === 'Unset')!
    await btn.trigger('click')
    expect(w.emitted('update')!.at(-1)).toEqual([''])
  })

  it('offers "leave it to the device" as a real option on a choice', async () => {
    const w = field(CHOICE, '1', { inheritedFrom: 'the device' })
    const blank = w.findAll('option').find((o) => o.attributes('value') === '')!
    expect(blank.text()).toContain('Leave it to the device')
    await w.find('select').setValue('')
    expect(w.emitted('update')!.at(-1)).toEqual([''])
  })

  it('labels the control and shows the real keyword', () => {
    const w = field(INT, '120')
    const id = w.find('input').attributes('id')
    expect(w.find(`label[for="${id}"]`).text()).toContain('Mouse speed')
    expect(w.text()).toContain('a_key')
  })

  it('explains what the setting does', () => {
    expect(field(INT, '120').text()).toContain('How fast the pointer moves.')
  })
})
