import { mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import FunctionDemo from './FunctionDemo.vue'
import { FUNCTION_DEMOS } from '@/learn/topics'

function matchMedia(reduce: boolean) {
  return vi.fn().mockReturnValue({
    matches: reduce,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  })
}

const toggleDemo = FUNCTION_DEMOS.find((d) => d.name === 'toggle')!

describe('FunctionDemo', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })
  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('shows the whole pattern, not just the current moment', () => {
    vi.stubGlobal('matchMedia', matchMedia(false))
    const w = mount(FunctionDemo, { props: { demo: toggleDemo } })
    // every tick of both tracks is drawn, so the shape is readable at a glance
    expect(w.findAll('.bar--in')).toHaveLength(toggleDemo.input.length)
    expect(w.findAll('.bar--out')).toHaveLength(toggleDemo.output.length)
    expect(w.findAll('.bar--in.on')).toHaveLength(toggleDemo.input.filter(Boolean).length)
  })

  it('moves a playhead over time', async () => {
    vi.stubGlobal('matchMedia', matchMedia(false))
    const w = mount(FunctionDemo, { props: { demo: toggleDemo } })
    const at = () => w.findAll('.bar--in').findIndex((b) => b.classes().includes('now'))
    const first = at()
    vi.advanceTimersByTime(400)
    await w.vm.$nextTick()
    expect(at()).not.toBe(first)
  })

  it('stops when the page asks it to', async () => {
    vi.stubGlobal('matchMedia', matchMedia(false))
    const w = mount(FunctionDemo, { props: { demo: toggleDemo, play: true } })
    const at = () => w.findAll('.bar--in').findIndex((b) => b.classes().includes('now'))
    expect(at()).toBeGreaterThanOrEqual(0)
    await w.setProps({ play: false })
    expect(at()).toBe(-1) // no playhead at all
    vi.advanceTimersByTime(2000)
    await w.vm.$nextTick()
    expect(at()).toBe(-1)
    await w.setProps({ play: true })
    expect(at()).toBeGreaterThanOrEqual(0)
  })

  it('never moves under reduced motion, not even for one frame', () => {
    vi.stubGlobal('matchMedia', matchMedia(true))
    // play: true is the page's default, and must still be overridden by the
    // system preference — otherwise the first render flashes a playhead
    const w = mount(FunctionDemo, { props: { demo: toggleDemo, play: true } })
    expect(w.findAll('.bar.now')).toHaveLength(0)
    vi.advanceTimersByTime(2000)
    expect(w.findAll('.bar.now')).toHaveLength(0)
    // the pattern is still fully visible, so nothing is lost
    expect(w.findAll('.bar--out.on')).toHaveLength(toggleDemo.output.filter(Boolean).length)
  })

  it('describes itself for a screen reader instead of relying on the picture', () => {
    vi.stubGlobal('matchMedia', matchMedia(false))
    const w = mount(FunctionDemo, { props: { demo: toggleDemo } })
    const img = w.find('[role="img"]')
    expect(img.attributes('aria-label')).toContain('toggle')
    expect(img.attributes('aria-label')).toContain(toggleDemo.plain)
  })

  it('stops its timer when it goes away', () => {
    vi.stubGlobal('matchMedia', matchMedia(false))
    const clear = vi.spyOn(globalThis, 'clearInterval')
    const w = mount(FunctionDemo, { props: { demo: toggleDemo } })
    w.unmount()
    expect(clear).toHaveBeenCalled()
  })
})
