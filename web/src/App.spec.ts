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

  it('opens the About dialog from the header, with the accessibility links', async () => {
    const w = mount(App, {
      attachTo: document.body,
      global: { stubs: { RouterLink: RouterLinkStub, RouterView: RouterViewStub } },
    })

    const about = w.find('header .about-btn')
    expect(about.text()).toBe('About')
    expect(document.querySelector('[role="dialog"]')).toBeNull()

    await about.trigger('click')

    const dialog = document.querySelector('[role="dialog"]')
    expect(dialog).not.toBeNull()
    expect(dialog?.getAttribute('aria-label')).toBe('About QuadStick Profile Studio')

    const hrefs = [...dialog!.querySelectorAll('a')].map((a) => a.getAttribute('href'))
    expect(hrefs).toEqual(
      expect.arrayContaining([
        'https://myaccessibility.ai',
        'https://www.youtube.com/@myaccessibility',
        'https://www.instagram.com/myaccessibility',
        'https://www.linkedin.com/in/chris-venter/',
      ]),
    )
    // external links must not hand the opener a window handle
    for (const a of dialog!.querySelectorAll('a[target="_blank"]')) {
      expect(a.getAttribute('rel')).toContain('noopener')
    }

    // each link carries its platform icon, hidden from screen readers: the label names it
    const linkItems = [...dialog!.querySelectorAll('.links li')]
    expect(linkItems).toHaveLength(4)
    for (const li of linkItems) {
      const icon = li.querySelector('svg.icon')
      expect(icon).not.toBeNull()
      expect(icon?.getAttribute('aria-hidden')).toBe('true')
      expect(icon?.querySelector('path')?.getAttribute('d')).toBeTruthy()
    }

    w.unmount()
  })
})
