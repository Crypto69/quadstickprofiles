import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import FindingsList from './FindingsList.vue'
import { validation } from '@/test/factories'

const withFindings = validation({
  errors: 1,
  warnings: 1,
  info: 1,
  findings: [
    { severity: 'error', mode: 2, row: 9, message: "Unknown output 'nope'" },
    { severity: 'warning', mode: 3, row: null, message: 'Mode 3 has no way out' },
    { severity: 'info', mode: 1, row: 7, message: 'Row 7 is a sequence' },
  ],
  consequence: {
    error: 'The QuadStick will not read this profile correctly.',
    warning: 'The QuadStick still loads this profile, but…',
    info: 'Nothing is broken.',
  },
})

describe('FindingsList', () => {
  it('hides info notes by default but keeps errors and warnings', () => {
    const w = mount(FindingsList, { props: { validation: withFindings } })
    expect(w.text()).toContain("Unknown output 'nope'")
    expect(w.text()).toContain('Mode 3 has no way out')
    expect(w.text()).not.toContain('is a sequence')
    expect(w.text()).toContain('1 more note not shown')
  })

  it('shows everything when asked', () => {
    const w = mount(FindingsList, {
      props: { validation: withFindings, collapseInfo: false },
    })
    expect(w.text()).toContain('is a sequence')
    expect(w.findAll('li')).toHaveLength(3)
  })

  it('states where each problem is', () => {
    const w = mount(FindingsList, { props: { validation: withFindings } })
    expect(w.text()).toContain('Mode 2, row 9')
    expect(w.text()).toContain('Mode 3') // no row on this one
  })

  it('leads with the device consequence, worst first', () => {
    const w = mount(FindingsList, { props: { validation: withFindings, collapseInfo: false } })
    const lines = w.findAll('.consequence').map((n) => n.text())
    expect(lines[0]).toContain('will not read')
    expect(lines[1]).toContain('still loads')
    expect(lines[2]).toContain('Nothing is broken')
  })

  it('says so plainly when the profile is clean', () => {
    const w = mount(FindingsList, { props: { validation: validation() } })
    expect(w.text()).toBe('No problems found.')
  })

  it('handles a missing validation without crashing', () => {
    const w = mount(FindingsList, { props: { validation: null } })
    expect(w.text()).toBe('No problems found.')
  })
})
