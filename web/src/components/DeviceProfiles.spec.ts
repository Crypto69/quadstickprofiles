import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import DeviceProfiles from './DeviceProfiles.vue'
import type { Backup } from '@/api/types'
import type { DriveState } from '@/desktop'
import { useBackupsStore } from '@/stores/backups'

function backup(paths: string[]): Backup {
  return {
    id: 1,
    created_at: '2026-11-22T10:30:00+00:00',
    file_count: paths.length,
    total_bytes: paths.length * 100,
    files: paths.map((path) => ({ path, size: 100 })),
  }
}

function withBackups(backups: Backup[]) {
  const store = useBackupsStore()
  store.backups = backups
  store.loaded = true
  return mount(DeviceProfiles)
}

type Wrapper = ReturnType<typeof withBackups>
const row = (w: Wrapper, i: number) => w.findAll('tbody tr')[i]!
const lit = (w: Wrapper, i: number) =>
  row(w, i).findAll('.leds i').map((d) => d.classes().find((c) => c !== 'on'))

describe('DeviceProfiles', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('asks for a backup when there is none', () => {
    const w = withBackups([])
    expect(w.text()).toContain('Back up the QuadStick above')
    expect(w.find('table').exists()).toBe(false)
  })

  it('numbers the profiles in device order, each with the lights that pick it', () => {
    const w = withBackups([
      backup(['zelda.csv', 'default.csv', 'prefs.csv', 'joystick.bin', 'apex.csv']),
    ])
    const rows = w.findAll('tbody tr')
    expect(rows.map((r) => r.find('.num').text())).toEqual(['1', '2', '3'])
    expect(rows.map((r) => r.find('.name').text())).toEqual([
      'default.csv', 'apex.csv', 'zelda.csv',
    ])
    expect(lit(w, 0)).toEqual(['purple', 'off', 'off', 'off', 'off'])
    expect(lit(w, 2)).toEqual(['off', 'off', 'purple', 'off', 'off'])
    // the pattern in words, for anyone who cannot see the dots
    expect(row(w, 1).text()).toContain('LED 2 purple')
    // five numbered lights across the top
    expect(w.findAll('thead .led-num').map((n) => n.text())).toEqual(['1', '2', '3', '4', '5'])
  })

  it('uses the device colours past file 5, and carries on to file 32', () => {
    const names = Array.from({ length: 34 }, (_, i) => `p${String(i).padStart(2, '0')}.csv`)
    const w = withBackups([backup(names)])
    expect(lit(w, 6)).toEqual(['off', 'purple', 'off', 'off', 'purple']) // 7 = 5 + 2
    expect(lit(w, 11)).toEqual(['off', 'purple', 'off', 'off', 'blue']) // 12 = 10 + 2
    // the profile switch goes past the 16 a mode can have
    expect(lit(w, 16)).toEqual(['off', 'purple', 'off', 'off', 'red']) // file 17
    expect(lit(w, 19)).toEqual(['blue', 'blue', 'blue', 'blue', 'blue']) // file 20
    expect(row(w, 31).text()).not.toContain('cannot pick')
    // and stops at 32: the file is on the drive, but nothing reaches it
    expect(row(w, 32).text()).toContain('past 32: the QuadStick cannot pick it')
    expect(lit(w, 32)).toEqual(['off', 'off', 'off', 'off', 'off'])
  })

  it('names a file the QuadStick leaves off the switch, and why', () => {
    const w = withBackups([backup(['default.csv', 'myprefs.csv', 'prefs.csv', 'cod.csv'])])
    expect(w.findAll('tbody .name').map((n) => n.text())).toEqual(['default.csv', 'cod.csv'])
    const note = w.find('.skipped').text()
    expect(note).toContain('myprefs.csv')
    expect(note).toContain('can never be picked')
    expect(note).not.toContain('default.csv')
  })

  it('reads the newest backup only', () => {
    const w = withBackups([backup(['new.csv']), backup(['old.csv'])])
    expect(w.findAll('tbody .name').map((n) => n.text())).toEqual(['new.csv'])
  })
})

describe('DeviceProfiles in the desktop app', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.useFakeTimers()
  })
  afterEach(() => {
    delete window.pywebview
    vi.useRealTimers()
  })

  function shell(state: DriveState) {
    const s = {
      reveal: vi.fn(),
      open_external: vi.fn(),
      quadstick_drive: vi.fn(async () => state),
      choose_quadstick_drive: vi.fn(async () => null),
    }
    window.pywebview = { api: s }
    return s
  }

  it('lists exactly what is on the drive now, and looks again every few seconds', async () => {
    const s = shell({
      found: true,
      name: 'Quad Stick',
      files: [
        { path: 'qstest.csv', size: 1 },
        { path: 'default.csv', size: 1 },
        { path: 'prefs.csv', size: 1 },
      ],
    })
    const w = withBackups([backup(['old.csv'])])
    await flushPromises()
    expect(w.text()).toContain('Reading the drive Quad Stick now')
    expect(w.findAll('tbody .name').map((n) => n.text())).toEqual(['default.csv', 'qstest.csv'])
    expect(s.quadstick_drive).toHaveBeenCalledTimes(1)
    await vi.advanceTimersByTimeAsync(3000)
    expect(s.quadstick_drive).toHaveBeenCalledTimes(2)
    w.unmount()
    await vi.advanceTimersByTimeAsync(9000)
    expect(s.quadstick_drive).toHaveBeenCalledTimes(2) // stops when the page closes
  })

  it('unplugged, says which drive it is looking for and shows the newest backup', async () => {
    shell({ found: false, name: 'Quad Stick', files: [] })
    const w = withBackups([backup(['old.csv'])])
    await flushPromises()
    expect(w.text()).toContain('Plug in the QuadStick')
    expect(w.text()).toContain('Quad Stick')
    expect(w.text()).toContain('newest backup')
    expect(w.findAll('tbody .name').map((n) => n.text())).toEqual(['old.csv'])
    w.unmount()
  })

  it('can be told which drive is the QuadStick', async () => {
    const s = shell({ found: false, name: 'QuadStick', files: [] })
    const w = withBackups([])
    await flushPromises()
    const choose = w.findAll('button').find((b) => b.text().includes('Choose the drive'))!
    await choose.trigger('click')
    expect(s.choose_quadstick_drive).toHaveBeenCalled()
    w.unmount()
  })
})
