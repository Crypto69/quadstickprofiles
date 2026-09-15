import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import BottomBar from './BottomBar.vue'

describe('BottomBar', () => {
  it('renders its content and reads as fine when nothing is wrong', () => {
    const w = mount(BottomBar, { slots: { default: '<p>No problems found.</p>' } })
    expect(w.text()).toContain('No problems found.')
    expect(w.classes()).toContain('is-ok')
  })

  it.each(['error', 'warning', 'info'] as const)('takes the %s colour from the worst finding', (s) => {
    const w = mount(BottomBar, { props: { severity: s } })
    expect(w.classes()).toContain(`is-${s}`)
    expect(w.classes()).not.toContain('is-ok')
  })
})
