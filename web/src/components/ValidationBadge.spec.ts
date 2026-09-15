import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import ValidationBadge from './ValidationBadge.vue'
import { validation } from '@/test/factories'

function badge(v: ReturnType<typeof validation> | null) {
  return mount(ValidationBadge, { props: { validation: v } })
}

describe('ValidationBadge', () => {
  it('says Clean when there is nothing to fix', () => {
    const w = badge(validation({ info: 4 }))
    expect(w.text()).toBe('Clean')
    expect(w.classes()).toContain('badge--ok')
  })

  it('counts warnings, singular and plural', () => {
    expect(badge(validation({ warnings: 1 })).text()).toBe('1 warning')
    expect(badge(validation({ warnings: 3 })).text()).toBe('3 warnings')
  })

  it('shows errors even when warnings outnumber them', () => {
    const w = badge(validation({ errors: 1, warnings: 9 }))
    expect(w.text()).toBe('1 error')
    expect(w.classes()).toContain('badge--error')
  })

  it('explains what the device does, using the API wording when given', () => {
    const w = badge(
      validation({ errors: 1, consequence: { error: 'The QuadStick will not read this profile.' } }),
    )
    expect(w.attributes('title')).toBe('The QuadStick will not read this profile.')
  })

  it('falls back to its own wording when the API sent none', () => {
    const w = badge(validation({ warnings: 1 }))
    expect(w.attributes('title')).toContain('Loads, but')
  })

  it('distinguishes "not checked" from "clean"', () => {
    const w = badge(null)
    expect(w.text()).toBe('Not checked')
    expect(w.classes()).toContain('badge--info')
  })
})
