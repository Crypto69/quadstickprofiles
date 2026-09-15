import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import FunctionPicker from './FunctionPicker.vue'
import { useCatalogStore } from '@/stores/catalog'
import { catalog, stubFetch } from '@/test/factories'
import type { FunctionParam } from '@/api/types'

/** The picker needs the real function list, including the ones that take parameters. */
function fullCatalog() {
  return catalog({
    functions: [
      { name: 'normal', max_params: 0, description: 'on while the input is active' },
      { name: 'toggle', max_params: 0, description: 'one action turns it on, the next turns it off' },
      { name: 'repeat', max_params: 2, description: 'auto-fires while held' },
      { name: 'less_than', max_params: 1, description: 'on below a pressure threshold' },
      { name: 'pulse', max_params: 2, description: 'one press, or several' },
      { name: 'duty', max_params: 1, description: 'pressure sets the on-time' },
      { name: 'force_off', max_params: 1, description: 'forces the output off' },
      { name: 'greater_than', max_params: 2, description: 'on above a pressure threshold' },
      { name: 'delay_on', max_params: 2, description: 'waits, then turns on' },
    ],
  })
}

async function setup(fn = 'normal', params: FunctionParam[] = []) {
  vi.stubGlobal('fetch', stubFetch({ '/api/catalog': fullCatalog() }))
  await useCatalogStore().load()
  return mount(FunctionPicker, { props: { fn, params } })
}

describe('FunctionPicker', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.unstubAllGlobals()
  })

  it('describes each function in plain English in the list itself', async () => {
    const w = await setup()
    const text = w.find('select').text()
    expect(text).toContain('on while the input is active')
    expect(text).toContain('auto-fires while held')
  })

  it('shows no parameter boxes for a function that takes none', async () => {
    const w = await setup('normal')
    expect(w.findAll('input[type="number"]')).toHaveLength(0)
  })

  it('shows exactly as many parameter boxes as the function accepts', async () => {
    expect((await setup('repeat', [5, 2000])).findAll('input[type="number"]')).toHaveLength(2)
    expect((await setup('less_than', [40])).findAll('input[type="number"]')).toHaveLength(1)
  })

  it('picks a function bare, the way every fixture row is written', async () => {
    const w = await setup('normal')
    await w.find('select').setValue('repeat')
    const [fn, params] = w.emitted('update')!.at(-1)!
    expect(fn).toBe('repeat')
    // the firmware applies its own defaults when a parameter is absent, so nothing is
    // written; the boxes show those defaults as placeholders instead
    expect(params).toEqual([])
    await w.setProps({ fn: 'repeat', params: [] })
    const placeholders = w.findAll('input[type="number"]').map((b) => b.attributes('placeholder'))
    expect(placeholders).toEqual(['5', '2000'])
  })

  it('names each parameter instead of showing param 1 and param 2', async () => {
    const w = await setup('repeat', [5, 2000])
    const labels = w.findAll('label').map((l) => l.text())
    expect(labels).toContain('Presses per second')
    expect(labels).toContain('Hold delay (ms)')
  })

  // From the firmware's DataFlow.c, via QCM's FunctionParameters.cs. A wrong label
  // here puts a number in the wrong slot on the device.
  it('labels the parameters the way the firmware reads them', async () => {
    const labelsFor = async (fn: string, params: number[]) =>
      (await setup(fn, params)).findAll('.params label').map((l) => l.text())
    const hintsFor = async (fn: string, params: number[]) =>
      (await setup(fn, params)).findAll('.params .hint').map((l) => l.text())

    // pulse: length, then a count — not a gap
    expect(await labelsFor('pulse', [100, 3])).toEqual(['Press length (ms)', 'Count'])
    expect((await hintsFor('pulse', [100, 3]))[1]).toMatch(/0 means one/)
    // duty: one cycle-length parameter, not a min/max pair
    expect(await labelsFor('duty', [100])).toEqual(['Cycle (ms)'])
    // force_off: a delay, not an output group
    expect(await labelsFor('force_off', [0])).toEqual(['Delay (ms)'])
    expect((await hintsFor('force_off', [0]))[0]).toMatch(/at once/)
    // greater_than: threshold and an upper limit, not hysteresis
    expect(await labelsFor('greater_than', [50, 90])).toEqual(['Threshold (%)', 'Upper limit (%)'])
    expect((await hintsFor('greater_than', [50, 90]))[1]).toMatch(/no upper limit/)
    // delay_on: exactly 1 latches
    expect((await hintsFor('delay_on', [200, 1]))[1]).toMatch(/exactly 1 means latch/)
  })

  it('lets the second parameter be set without touching the first', async () => {
    const w = await setup('repeat', [])
    const boxes = w.findAll('input[type="number"]')
    await boxes[1]!.setValue('3000')
    const [, params] = w.emitted('update')!.at(-1)! as [string, number[]]
    expect(params).toHaveLength(2)
    expect(params[1]).toBe(3000)
    expect(params[0]).toBe(5) // filled with the firmware default, not left undefined
  })

  it('drops a parameter, and everything after it, when its box is cleared', async () => {
    // parameters are positional: the firmware cannot skip a slot
    const w = await setup('repeat', [5, 2000])
    const boxes = w.findAll('input[type="number"]')
    await boxes[1]!.setValue('')
    expect((w.emitted('update')!.at(-1)! as [string, number[]])[1]).toEqual([5])
    await boxes[0]!.setValue('')
    expect((w.emitted('update')!.at(-1)! as [string, number[]])[1]).toEqual([])
  })

  it('treats a non-numeric entry as empty rather than emitting 0', async () => {
    const w = await setup('less_than', [40])
    await w.find('input[type="number"]').setValue('abc')
    const [, params] = w.emitted('update')!.at(-1)! as [string, number[]]
    expect(params).toEqual([])
  })

  it('truncates a decimal the way the firmware would', async () => {
    const w = await setup('less_than', [40])
    await w.find('input[type="number"]').setValue('2.5')
    expect((w.emitted('update')!.at(-1)! as [string, number[]])[1]).toEqual([2])
  })

  it('bounds each box to what the firmware can store', async () => {
    const w = await setup('repeat', [5, 2000])
    for (const box of w.findAll('input[type="number"]')) {
      expect(box.attributes('min')).toBe('0')
      expect(box.attributes('step')).toBe('1')
      expect(box.attributes('max')).toBe('16383')
    }
  })

  // The file may hold a token the firmware cannot read as a number. A number box
  // renders such a value blank, so the token would vanish from the screen and the
  // first keystroke would silently delete it from the file.
  it('shows a non-numeric parameter as text, flagged, instead of an empty box', async () => {
    const w = await setup('repeat', ['five', 2000])
    const boxes = w.findAll('.params input')
    expect(boxes).toHaveLength(2)
    expect(boxes[0]!.attributes('type')).toBe('text')
    expect((boxes[0]!.element as HTMLInputElement).value).toBe('five')
    expect(boxes[0]!.attributes('aria-invalid')).toBe('true')
    expect(w.text()).toContain('the QuadStick reads it as 0')

    // the numeric one beside it is unaffected
    expect(boxes[1]!.attributes('type')).toBe('number')
    expect(boxes[1]!.attributes('aria-invalid')).toBeUndefined()
  })

  it('replaces a non-numeric parameter with what is typed over it', async () => {
    const w = await setup('repeat', ['five', 2000])
    await w.findAll('.params input')[0]!.setValue('5')
    expect((w.emitted('update')!.at(-1)! as [string, FunctionParam[]])[1]).toEqual([5, 2000])
  })

  it('takes that bound from the catalog, not from a number of its own', async () => {
    const c = fullCatalog()
    c.limits = { ...c.limits, max_function_param: 4095 }
    vi.stubGlobal('fetch', stubFetch({ '/api/catalog': c }))
    await useCatalogStore().load()
    const w = mount(FunctionPicker, { props: { fn: 'repeat', params: [5, 2000] } })
    for (const box of w.findAll('input[type="number"]')) {
      expect(box.attributes('max')).toBe('4095')
    }
  })
})
