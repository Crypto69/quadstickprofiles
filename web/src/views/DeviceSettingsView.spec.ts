import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import DeviceSettingsView from './DeviceSettingsView.vue'
import { catalog, fileResponse, prefs, stubFetch, validation } from '@/test/factories'

const RouterLinkStub = { props: ['to'], template: '<a :href="String(to)"><slot /></a>' }

async function settle(times = 6) {
  for (let i = 0; i < times; i++) await Promise.resolve()
  await new Promise((r) => setTimeout(r, 0))
}

async function page(routes: Record<string, unknown> = {}) {
  vi.stubGlobal(
    'fetch',
    stubFetch({
      '/api/catalog': catalog(),
      // the page judges the settings against the owner's firmware, so every call says which
      '/api/prefs?firmware=2373': prefs({ volume: '40' }),
      ...routes,
    }),
  )
  const w = mount(DeviceSettingsView, {
    attachTo: document.body,
    global: { stubs: { RouterLink: RouterLinkStub } },
  })
  await settle()
  return w
}

describe('DeviceSettingsView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.unstubAllGlobals()
    document.body.innerHTML = ''
  })
  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('states the precedence, device first', async () => {
    const w = await page()
    const steps = w.findAll('.precedence li').map((l) => l.text())
    expect(steps).toHaveLength(3)
    expect(steps[0]).toContain('prefs.csv')
    expect(steps[1]).toContain('profile')
    expect(steps[2]).toContain('mode')
  })

  it('loads the device settings into typed controls', async () => {
    const w = await page()
    const volume = w.find<HTMLInputElement>('#pref-volume')
    expect(volume.element.value).toBe('40')
    expect(volume.attributes('max')).toBe('100')
  })

  it('warns when a device-wide setting would hide the flash drive', async () => {
    // decided from the catalog's firmware table, not from the API's wording: the
    // API here reports nothing at all, and the page still warns
    const w = await page({ '/api/prefs?firmware=2373': prefs({ enable_DS3_emulation: '6' }) })
    expect(w.find('.warn').text()).toContain('hides the flash drive')
    expect(w.find('.warn').text()).toContain('every profile')
  })

  it('judges the drive warning against the firmware shown, and tells the API which', async () => {
    const fetchMock = stubFetch({
      '/api/catalog': catalog(),
      '/api/prefs?firmware=2373': prefs({ enable_DS3_emulation: '6' }),
      '/api/prefs?firmware=1476': prefs({ enable_DS3_emulation: '6' }),
    })
    vi.stubGlobal('fetch', fetchMock)
    const w = mount(DeviceSettingsView, {
      attachTo: document.body,
      global: { stubs: { RouterLink: RouterLinkStub } },
    })
    await settle()
    expect(w.find<HTMLSelectElement>('#prefs-fw').element.value).toBe('2373')
    expect(w.find('.warn').exists()).toBe(true) // 6 hides the drive on 2373

    await w.find('#prefs-fw').setValue('1476')
    await settle()
    // reloaded against the other firmware, where 6 does not hide the drive
    expect(fetchMock.mock.calls.some((c) => String(c[0]).endsWith('/api/prefs?firmware=1476'))).toBe(true)
    expect(w.find('.warn').exists()).toBe(false)
    w.unmount()
  })

  it('warns live as the value is edited, before anything is saved', async () => {
    const w = await page({ '/api/prefs?firmware=2373': prefs({ enable_DS3_emulation: '4' }) })
    expect(w.find('.warn').exists()).toBe(false)
    const store = (await import('@/stores/prefs')).usePrefsStore()
    store.set('enable_DS3_emulation', '7')
    await settle()
    expect(w.find('.warn').text()).toContain('hides the flash drive')
  })

  it('shows why a save was refused, without throwing the edit away', async () => {
    const refusal = validation({
      errors: 1,
      findings: [
        { severity: 'error', mode: null, row: null, message: 'Speaker volume (volume) is 900; the highest the QuadStick accepts is 100' },
      ],
    })
    const w = await page({
      'PUT /api/prefs?firmware=2373': {
        status: 422,
        body: JSON.stringify({ detail: { message: 'Some settings are outside what the QuadStick accepts', validation: refusal } }),
        headers: { 'Content-Type': 'application/json' },
      },
    })
    await w.find('#pref-volume').setValue('900')
    await settle()
    const save = w.findAll('button').find((b) => b.text() === 'Save')!
    await save.trigger('click')
    await settle()
    expect(w.text()).toContain('were not saved')
    expect(w.text()).toContain('the highest the QuadStick accepts')
    expect(w.find<HTMLInputElement>('#pref-volume').element.value).toBe('900')
  })

  it('only enables save once something changed', async () => {
    const w = await page()
    const save = () => w.findAll('button').find((b) => b.text().startsWith('Save'))!
    expect(save().attributes('disabled')).toBeDefined()
    await w.find('#pref-volume').setValue('55')
    await settle()
    expect(save().attributes('disabled')).toBeUndefined()
  })

  it('exports prefs.csv and then explains how to install it', async () => {
    const click = vi.fn()
    const orig = document.createElement.bind(document)
    vi.spyOn(document, 'createElement').mockImplementation((tag: string) => {
      const el = orig(tag) as HTMLElement
      if (tag === 'a') el.click = click
      return el
    })
    const w = await page({
      '/api/prefs/export.csv?firmware=2373': fileResponse('Preferences,\r\n', {
        filename: 'prefs.csv', contentType: 'text/csv', exportPath: '/app/exports/prefs.csv',
      }),
    })
    await w.findAll('button').find((b) => b.text().includes('Export prefs.csv'))!.trigger('click')
    await settle()
    expect(click).toHaveBeenCalled()
    const dialog = document.body.textContent ?? ''
    expect(dialog).toContain('Put these settings on the QuadStick')
    expect(dialog).toContain('replacing the one already there')
    // and it reminds you not to touch default.csv, which is a different file
    expect(dialog).toContain('default.csv')
    // the drive is only re-read at power-on, and boot throws away anything not a .csv
    expect(dialog).toMatch(/only re-reads its drive at power-on/i)
    expect(dialog).toContain('joystick.bin')
    expect(dialog).toMatch(/keep backups off the stick/i)
    w.unmount()
  })

  it('imports a prefs.csv from the flash drive', async () => {
    const w = await page({ 'POST /api/prefs/import?firmware=2373': prefs({ brightness: '9' }) })
    const store = (await import('@/stores/prefs')).usePrefsStore()
    await store.importFile(new File(['x'], 'prefs.csv'))
    await settle()
    expect(store.values).toEqual({ brightness: '9' })
    expect(w.find<HTMLInputElement>('#pref-volume').element.value).toBe('')
  })

  it('takes only a .csv', async () => {
    const w = await page()
    expect(w.find('input[type="file"]').attributes('accept')).toBe('.csv')
  })
})
