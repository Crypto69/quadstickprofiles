import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'
import App from './App.vue'
import { catalog, stubFetch } from '@/test/factories'

const RouterLinkStub = { props: ['to'], template: '<a :href="String(to)"><slot /></a>' }
const RouterViewStub = { template: '<div />' }

describe('App header', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    stubFetch({ '/api/catalog': catalog() })
  })

  it('shows the logo mark next to the name, with the name as the accessible text', () => {
    const w = mount(App, { global: { stubs: { RouterLink: RouterLinkStub, RouterView: RouterViewStub } } })
    const brand = w.find('header .brand')
    expect(brand.find('img.brand__mark').exists()).toBe(true)
    expect(brand.find('img.brand__mark').attributes('alt')).toBe('')   // decorative: the text carries the name
    expect(brand.text()).toBe('QuadStick Profile Studio')
  })

  it('shows the deployed version at the end of the header', () => {
    const w = mount(App, { global: { stubs: { RouterLink: RouterLinkStub, RouterView: RouterViewStub } } })
    const badge = w.find('header .version')
    expect(badge.exists()).toBe(true)
    // "dev" under vitest; deploy.sh bakes 1.0, 1.1 ... into the real build
    expect(badge.text()).toBe('vdev')
  })
})
