import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import LearnTopicView from './LearnTopicView.vue'
import { TOPICS } from '@/learn/topics'
import { useCatalogStore } from '@/stores/catalog'
import { catalog, stubFetch } from '@/test/factories'

const RouterLinkStub = { props: ['to'], template: '<a :href="String(to)"><slot /></a>' }

async function page(slug: string) {
  vi.stubGlobal('fetch', stubFetch({ '/api/catalog': catalog() }))
  await useCatalogStore().load()
  return mount(LearnTopicView, {
    props: { slug },
    global: { stubs: { RouterLink: RouterLinkStub } },
  })
}

describe('LearnTopicView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.unstubAllGlobals()
  })

  it('renders every topic with real content, not an empty shell', async () => {
    for (const t of TOPICS) {
      const w = await page(t.slug)
      expect(w.find('h1').text()).toBe(t.title)
      // each page has substantive body text beyond its own heading and blurb
      const body = w.text().replace(t.title, '').replace(t.blurb, '')
      expect(body.length).toBeGreaterThan(300)
    }
  })

  it('says so politely for an unknown page', async () => {
    const w = await page('nope')
    expect(w.text()).toContain('does not exist')
  })

  it('links forward and back, but not off either end', async () => {
    const first = await page(TOPICS[0]!.slug)
    expect(first.findAll('.pager a')).toHaveLength(1) // next only
    const middle = await page(TOPICS[3]!.slug)
    expect(middle.findAll('.pager a')).toHaveLength(2)
    const last = await page(TOPICS.at(-1)!.slug)
    expect(last.findAll('.pager a')).toHaveLength(1) // previous only
  })

  it('builds the LED table from the same rule as the printed card', async () => {
    const w = await page('lights')
    const rows = w.findAll('.leds-table tbody tr')
    expect(rows).toHaveLength(16) // every mode the QuadStick reads
    const lampsIn = (i: number) =>
      rows[i]!.findAll('.leds i').map((n) => n.classes().includes('on'))
    expect(lampsIn(0)).toEqual([true, false, false, false, false]) // mode 1
    expect(lampsIn(4)).toEqual([false, false, false, false, true]) // mode 5
    expect(lampsIn(6)).toEqual([false, true, false, false, true]) // mode 7 = 5 + 2
    expect(lampsIn(9)).toEqual([false, false, false, false, true]) // mode 10 = LED 5, blue
  })

  it('tells mode 10 from mode 5 by colour, and says so in words', async () => {
    const w = await page('lights')
    const rows = w.findAll('.leds-table tbody tr')
    const colourOf = (i: number) =>
      rows[i]!.findAll('.leds i').map(
        (n) => ['purple', 'blue', 'red'].find((c) => n.classes().includes(c)) ?? 'off',
      )
    expect(colourOf(4)).toEqual(['off', 'off', 'off', 'off', 'purple'])
    expect(colourOf(9)).toEqual(['off', 'off', 'off', 'off', 'blue'])
    expect(colourOf(15)).toEqual(['purple', 'off', 'off', 'off', 'red'])
    expect(rows[4]!.text()).toContain('LED 5 purple')
    expect(rows[9]!.text()).toContain('LED 5 blue')
    expect(rows[15]!.text()).toContain('LED 1 purple and LED 5 red')
    // nothing "looks exactly like" anything any more
    expect(w.text()).not.toContain('looks exactly like')
    expect(w.text()).toContain('purple for 5, blue for 10')
  })

  it('takes the drive-hiding modes from the catalog, per firmware', async () => {
    const w = await page('safety')
    const text = w.text()
    expect(text).toContain('2373')
    expect(text).toContain('5, 6, 7')
    expect(text).toContain('1476')
    expect(text).toContain('3, 5, 7')
    // and it says which one is the owner's
    expect(text).toContain('this is the one your device runs')
  })

  it('warns about default.csv in the terms that matter', async () => {
    const w = await page('safety')
    const text = w.text()
    expect(text).toContain('default.csv')
    expect(text).toMatch(/flash drive stops appearing/i)
    expect(text).toMatch(/hardware reset/i)
  })

  it('animates every function with both tracks', async () => {
    const w = await page('functions')
    const demos = w.findAll('.demo')
    expect(demos.length).toBeGreaterThanOrEqual(8)
    for (const d of demos) {
      expect(d.findAll('.track')).toHaveLength(2) // what you do, what the console sees
      expect(d.findAll('.bar').length).toBeGreaterThan(10)
    }
  })

  it('governs all nine animations with one control, not nine', async () => {
    const w = await page('functions')
    const buttons = w.findAll('button')
    expect(buttons).toHaveLength(1)
    expect(buttons[0]!.text()).toContain('Stop the pictures moving')
    await buttons[0]!.trigger('click')
    expect(w.find('button').text()).toContain('Start the pictures moving')
  })

  it('shows the worked patterns with their source file named', async () => {
    const w = await page('patterns')
    const text = w.text()
    expect(text).toContain('ddfortnite.csv')
    expect(text).toContain('cod.csv')
    expect(text).toContain('left_2')
    expect(text).toContain('toggle')
  })

  it('gets the settings precedence the right way round', async () => {
    const w = await page('settings')
    const items = w.findAll('.precedence li').map((l) => l.text())
    expect(items).toHaveLength(3)
    expect(items[0]).toContain('prefs.csv')
    expect(items[1]).toContain('profile')
    expect(items[2]).toContain('mode')
    // and it is honest that the per-mode kind is unverified
    expect(w.text()).toContain('not')
    expect(w.text()).toContain('tried on your device yet')
  })

  it('describes the file-change gesture in the right order', async () => {
    const w = await page('changing-mode')
    const steps = w.findAll('.steps li').map((l) => l.text())
    // the intro counts the steps it then lists: three, not four
    expect(steps).toHaveLength(3)
    expect(w.text()).toContain('three-part move')
    expect(w.text()).not.toContain('four-part')
    expect(steps[0]).toMatch(/long hard sip/i)
    expect(steps[1]).toMatch(/joystick/i)
    expect(steps[2]).toMatch(/lip/i)
  })

  it('gives alt text to every photo it uses', async () => {
    for (const slug of ['files-and-modes', 'soft-and-hard', 'safety']) {
      const w = await page(slug)
      for (const img of w.findAll('img')) {
        expect((img.attributes('alt') ?? '').length).toBeGreaterThan(15)
      }
    }
  })
})
