import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import DriveBackups from './DriveBackups.vue'
import type { Backup } from '@/api/types'
import { fileResponse, noContent, stubFetch } from '@/test/factories'

function backup(over: Partial<Backup> = {}): Backup {
  return {
    id: 1,
    created_at: '2026-11-22T10:30:00+00:00',
    file_count: 2,
    total_bytes: 2048,
    files: [
      { path: 'default.csv', size: 1024 },
      { path: 'joystick.bin', size: 1024 },
    ],
    ...over,
  }
}

function button(label: string) {
  return [...document.body.querySelectorAll('button')].find((b) =>
    (b.textContent ?? '').trim().includes(label),
  )
}

async function settle(times = 6) {
  for (let i = 0; i < times; i++) await Promise.resolve()
  await new Promise((r) => setTimeout(r, 0))
}

function picked(relativePath: string): File {
  const f = new File(['x'], relativePath.split('/').pop()!)
  Object.defineProperty(f, 'webkitRelativePath', { value: relativePath })
  return f
}

describe('DriveBackups', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.unstubAllGlobals()
    delete window.pywebview
    document.body.innerHTML = ''
  })
  afterEach(() => {
    delete window.pywebview
    document.body.innerHTML = ''
  })

  it('says when the drive was last backed up', async () => {
    vi.stubGlobal('fetch', stubFetch({ '/api/backups': [backup({ id: 2 }), backup()] }))
    const w = mount(DriveBackups, { attachTo: document.body })
    await settle()
    expect(w.text()).toContain('Last backed up')
    expect(w.text()).toContain('2026')
    expect(w.text()).toContain('2 files')
    w.unmount()
  })

  it('says it has never been backed up, and offers no restore', async () => {
    vi.stubGlobal('fetch', stubFetch({ '/api/backups': [] }))
    const w = mount(DriveBackups, { attachTo: document.body })
    await settle()
    expect(w.text()).toContain('Not backed up yet')
    expect(button('Restore a backup')?.disabled).toBe(true)
    w.unmount()
  })

  it('backs up every file from the picked drive, with its path on the drive', async () => {
    const fetch = stubFetch({ '/api/backups': [], 'POST /api/backups': backup({ id: 7 }) })
    vi.stubGlobal('fetch', fetch)
    const w = mount(DriveBackups, { attachTo: document.body })
    await settle()

    const input = w.find('input[type="file"]')
    expect(input.attributes()).toHaveProperty('webkitdirectory')
    Object.defineProperty(input.element, 'files', {
      value: [picked('QUADSTICK/default.csv'), picked('QUADSTICK/.fseventsd/x'), picked('QUADSTICK/joystick.bin')],
    })
    await input.trigger('change')
    await settle()

    const [, init] = fetch.mock.calls.find(([, i]) => i?.method === 'POST')!
    const form = init!.body as FormData
    expect(form.getAll('paths')).toEqual(['default.csv', 'joystick.bin'])
    expect(form.getAll('files')).toHaveLength(2)
    expect(w.find('[role="status"]').text()).toContain('Backed up 2 files')
    w.unmount()
  })

  it('shows why a backup was refused', async () => {
    vi.stubGlobal(
      'fetch',
      stubFetch({
        '/api/backups': [],
        'POST /api/backups': {
          status: 422,
          body: JSON.stringify({ detail: 'That folder has no .csv profiles at its top level' }),
          headers: { 'Content-Type': 'application/json' },
        },
      }),
    )
    const w = mount(DriveBackups, { attachTo: document.body })
    await settle()
    const input = w.find('input[type="file"]')
    Object.defineProperty(input.element, 'files', { value: [picked('Pictures/cat.jpg')] })
    await input.trigger('change')
    await settle()
    expect(w.find('[role="alert"]').text()).toContain('no .csv profiles')
    w.unmount()
  })

  function desktop(over: Record<string, unknown> = {}) {
    const shell = {
      reveal: vi.fn(),
      open_external: vi.fn(),
      quadstick_drive: vi.fn(async () => ({ found: true, name: 'Quad Stick', files: [] })),
      read_quadstick_drive: vi.fn(async () => [{ path: 'default.csv', data: btoa('QuadStick') }]),
      choose_quadstick_drive: vi.fn(async () => null),
      ...over,
    }
    window.pywebview = { api: shell }
    return shell
  }

  it('in the desktop build reads the drive itself, with no folder dialog', async () => {
    const shell = desktop()
    const fetch = stubFetch({ '/api/backups': [], 'POST /api/backups': backup({ id: 3, file_count: 1 }) })
    vi.stubGlobal('fetch', fetch)
    const w = mount(DriveBackups, { attachTo: document.body })
    await settle()
    button('Back up the QuadStick')!.click()
    await settle()
    expect(shell.read_quadstick_drive).toHaveBeenCalled()
    expect(shell.choose_quadstick_drive).not.toHaveBeenCalled()
    const [, init] = fetch.mock.calls.find(([, i]) => i?.method === 'POST')!
    expect((init!.body as FormData).getAll('paths')).toEqual(['default.csv'])
    expect(w.text()).toContain('Backed up 1 file')
    w.unmount()
  })

  it('in the desktop build asks which drive only when it cannot find one', async () => {
    const read = vi
      .fn()
      .mockResolvedValueOnce(null)
      .mockResolvedValueOnce([{ path: 'default.csv', data: btoa('QuadStick') }])
    const shell = desktop({
      read_quadstick_drive: read,
      choose_quadstick_drive: vi.fn(async () => ({ found: true, name: 'QS', files: [] })),
    })
    const fetch = stubFetch({ '/api/backups': [], 'POST /api/backups': backup({ id: 3, file_count: 1 }) })
    vi.stubGlobal('fetch', fetch)
    const w = mount(DriveBackups, { attachTo: document.body })
    await settle()
    button('Back up the QuadStick')!.click()
    await settle()
    expect(shell.choose_quadstick_drive).toHaveBeenCalled()
    expect(read).toHaveBeenCalledTimes(2)
    expect(fetch.mock.calls.some(([, i]) => i?.method === 'POST')).toBe(true)
    w.unmount()
  })

  it('in the desktop build backs up nothing when the drive dialog is cancelled', async () => {
    desktop({ read_quadstick_drive: vi.fn(async () => null) })
    const fetch = stubFetch({ '/api/backups': [] })
    vi.stubGlobal('fetch', fetch)
    const w = mount(DriveBackups, { attachTo: document.body })
    await settle()
    button('Back up the QuadStick')!.click()
    await settle()
    expect(fetch.mock.calls.some(([, i]) => i?.method === 'POST')).toBe(false)
    expect(button('Back up the QuadStick')!.disabled).toBe(false)
    w.unmount()
  })

  it('restores the chosen backup as a .zip named for its local time', async () => {
    const zip = fileResponse('PK', { filename: 'x.zip', contentType: 'application/zip' })
    const fetch = stubFetch({ '/api/backups': [backup({ id: 2 }), backup()] })
    vi.stubGlobal('fetch', async (input: RequestInfo | URL, init?: RequestInit) =>
      String(input).startsWith('/api/backups/1/download.zip')
        ? new Response(zip.body, { status: 200, headers: zip.headers })
        : fetch(input, init),
    )
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    const w = mount(DriveBackups, { attachTo: document.body })
    await settle()

    button('Restore a backup')!.click()
    await settle()
    const radios = document.body.querySelectorAll<HTMLInputElement>('input[name="backup"]')
    expect(radios).toHaveLength(2)
    expect(radios[0]!.checked).toBe(true) // the newest is chosen to start with
    radios[1]!.click()
    await settle()
    button('Save the backup')!.click()
    await settle()

    expect(click).toHaveBeenCalled()
    expect(document.body.textContent).toContain('Copy those files to the top level')
    expect(document.body.textContent).toContain('Saved as')
    w.unmount()
  })

  it('deletes a backup only after a second, explicit yes', async () => {
    const fetch = stubFetch({ '/api/backups': [backup()], 'DELETE /api/backups/1': noContent() })
    vi.stubGlobal('fetch', fetch)
    const w = mount(DriveBackups, { attachTo: document.body })
    await settle()
    button('Restore a backup')!.click()
    await settle()
    button('Delete this backup')!.click()
    await settle()
    expect(fetch.mock.calls.some(([, i]) => i?.method === 'DELETE')).toBe(false)
    button('Yes, delete it')!.click()
    await settle()
    expect(fetch.mock.calls.some(([, i]) => i?.method === 'DELETE')).toBe(true)
    expect(w.text()).toContain('Not backed up yet')
    w.unmount()
  })
})
