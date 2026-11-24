import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import ReplaceDrive from './ReplaceDrive.vue'
import type { Backup } from '@/api/types'
import type { DriveState } from '@/desktop'
import { useDriveStore } from '@/stores/drive'
import { fileResponse, stubFetch, summary, validation } from '@/test/factories'

const ON_DRIVE: DriveState = {
  found: true,
  name: 'Quad Stick',
  files: [
    { path: 'default.csv', size: 1 },
    { path: 'old.csv', size: 1 },
    { path: 'prefs.csv', size: 1 },
  ],
}

const BACKUP: Backup = {
  id: 9,
  created_at: '2026-11-24T10:30:00+00:00',
  file_count: 3,
  total_bytes: 3,
  files: ON_DRIVE.files,
}

const PROFILES = [
  summary({ id: 1, name: 'Apex', csv_filename: 'apex.csv' }),
  summary({ id: 2, name: 'Broken', csv_filename: 'broken.csv', validation: validation({ errors: 2 }) }),
  summary({ id: 3, name: 'Apex (older)', csv_filename: 'APEX.csv' }),
  summary({ id: 4, name: 'Cod', csv_filename: 'cod.csv' }),
]

function csv(name: string) {
  return fileResponse(`QuadStick Configuration,${name}\r\n`, { filename: name, contentType: 'text/csv' })
}

function button(label: string) {
  return [...document.body.querySelectorAll('button')].find((b) =>
    (b.textContent ?? '').trim().includes(label),
  )!
}

const dialog = () => document.body.querySelector('[role="dialog"]')?.textContent ?? ''

async function settle(times = 8) {
  for (let i = 0; i < times; i++) {
    await Promise.resolve()
    await new Promise((r) => setTimeout(r, 0))
  }
}

function shell(over: Record<string, unknown> = {}) {
  const s = {
    reveal: vi.fn(),
    open_external: vi.fn(),
    quadstick_drive: vi.fn(async () => ON_DRIVE),
    read_quadstick_drive: vi.fn(async () => [{ path: 'default.csv', data: btoa('QuadStick') }]),
    choose_quadstick_drive: vi.fn(async () => null),
    write_quadstick_drive: vi.fn(async (files: { name: string }[]) => ({
      ...ON_DRIVE,
      files: [{ path: 'default.csv', size: 1 }, ...files.map((f) => ({ path: f.name, size: 1 }))],
    })),
    ...over,
  }
  window.pywebview = { api: s }
  return s
}

function mountIt(state: DriveState = ON_DRIVE) {
  useDriveStore().state = state
  return mount(ReplaceDrive, {
    attachTo: document.body,
    global: { stubs: { RouterLink: { template: '<a><slot /></a>' } } },
  })
}

const routes = {
  '/api/profiles?validate=true': PROFILES,
  'POST /api/backups': BACKUP,
  '/api/profiles/1/export.csv': csv('apex.csv'),
  '/api/profiles/4/export.csv': csv('cod.csv'),
}

describe('ReplaceDrive', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    document.body.innerHTML = ''
  })
  afterEach(() => {
    delete window.pywebview
    vi.unstubAllGlobals()
    document.body.innerHTML = ''
  })

  it('cannot start until the QuadStick is plugged in', () => {
    shell()
    const w = mountIt({ found: false, name: 'Quad Stick', files: [] })
    expect(button('Put my profiles on the QuadStick').disabled).toBe(true)
    w.unmount()
  })

  it('ticks every profile that can go on, once per file name, and shows the drive after', async () => {
    shell()
    vi.stubGlobal('fetch', stubFetch(routes))
    const w = mountIt()
    button('Put my profiles on the QuadStick').click()
    await settle()

    const boxes = [...document.body.querySelectorAll<HTMLInputElement>('input[type="checkbox"]')]
    // Broken has no checkbox; of apex.csv and APEX.csv the newest (first) is ticked
    expect(boxes.map((b) => b.checked)).toEqual([true, false, true])
    expect(dialog()).toContain('Has 2 errors, so it cannot go on')
    const after = [...document.body.querySelectorAll('.after-list li')].map((li) => li.textContent)
    expect(after.map((t) => t?.replace(/\s+/g, ' ').trim())).toEqual([
      expect.stringContaining('1'),
      expect.stringContaining('apex.csv'),
      expect.stringContaining('cod.csv'),
    ])
    expect(after[0]).toContain('default.csv')
    expect(dialog()).toContain('default.csv stays as it is')
    expect(dialog()).toContain('Taken off the drive: old.csv')
    expect(button('Back up, then put 2 profiles on').disabled).toBe(false)

    // ticking the older apex.csv as well is two files with one name
    boxes[1]!.click()
    await settle(1)
    expect(dialog()).toContain('Two ticked profiles are called apex.csv')
    expect(button('Back up, then put 3 profiles on').disabled).toBe(true)
    w.unmount()
  })

  it('backs up, exports each ticked profile, and hands them to the shell', async () => {
    const s = shell()
    const fetch = stubFetch(routes)
    vi.stubGlobal('fetch', fetch)
    const w = mountIt()
    button('Put my profiles on the QuadStick').click()
    await settle()
    button('Back up, then put 2 profiles on').click()
    await settle()

    expect(s.read_quadstick_drive).toHaveBeenCalled()
    const calls = fetch.mock.calls.map(([u, i]) => `${i?.method ?? 'GET'} ${u}`)
    expect(calls.indexOf('POST /api/backups')).toBeLessThan(calls.indexOf('GET /api/profiles/1/export.csv'))
    expect(s.write_quadstick_drive).toHaveBeenCalledWith([
      { name: 'apex.csv', data: btoa('QuadStick Configuration,apex.csv\r\n') },
      { name: 'cod.csv', data: btoa('QuadStick Configuration,cod.csv\r\n') },
    ])
    expect(dialog()).toContain('Done. The QuadStick drive has 3 profiles on it now')
    expect(dialog()).toContain('safe to unplug')
    expect(dialog()).toContain('Unplug the QuadStick and plug it back in')
    w.unmount()
  })

  it('says what the shell refused, and where the drive as it was is kept', async () => {
    const s = shell({
      write_quadstick_drive: vi.fn(async () => {
        throw { message: 'There is not enough room on the QuadStick drive. Nothing was changed.' }
      }),
    })
    vi.stubGlobal('fetch', stubFetch(routes))
    const w = mountIt()
    button('Put my profiles on the QuadStick').click()
    await settle()
    button('Back up, then put 2 profiles on').click()
    await settle()
    expect(s.write_quadstick_drive).toHaveBeenCalled()
    const alert = document.body.querySelector('[role="alert"]')!.textContent
    expect(alert).toContain('not enough room')
    expect(alert).toContain('has the drive as it was')
    // and it can be tried again
    expect(button('Back up, then put 2 profiles on').disabled).toBe(false)
    w.unmount()
  })

  it('writes nothing when the QuadStick was unplugged before the backup', async () => {
    const s = shell({ read_quadstick_drive: vi.fn(async () => null) })
    vi.stubGlobal('fetch', stubFetch(routes))
    const w = mountIt()
    button('Put my profiles on the QuadStick').click()
    await settle()
    button('Back up, then put 2 profiles on').click()
    await settle()
    expect(s.write_quadstick_drive).not.toHaveBeenCalled()
    expect(document.body.querySelector('[role="alert"]')!.textContent).toContain('not plugged in')
    w.unmount()
  })
})
