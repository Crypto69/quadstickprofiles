import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import ExportChecklist from './ExportChecklist.vue'
import type { Download } from '@/api/client'

function download(over: Partial<Download> = {}): Download {
  return {
    blob: new Blob(['QuadStick Configuration,Version 1.4,,x\r\n'], { type: 'text/csv' }),
    filename: 'ddfortnite.csv',
    exportPath: '/app/exports/ddfortnite.csv',
    ...over,
  }
}

function open(dl: Download | null = download()) {
  return mount(ExportChecklist, {
    props: { open: true, download: dl, profileName: 'ddfortnite' },
    attachTo: document.body,
  })
}

describe('ExportChecklist', () => {
  it('names the file and where the server also put it', () => {
    const w = open()
    expect(document.body.textContent).toContain('ddfortnite.csv')
    expect(document.body.textContent).toContain('/app/exports/ddfortnite.csv')
    w.unmount()
  })

  it('warns about default.csv, because breaking it needs a hardware reset', () => {
    const w = open()
    const text = document.body.textContent ?? ''
    expect(text).toContain('default.csv')
    expect(text).toMatch(/hardware reset/i)
    w.unmount()
  })

  it('gives the on-device file-selection steps in order', () => {
    const w = open()
    const text = document.body.textContent ?? ''
    expect(text).toMatch(/long hard sip on the side tube/i)
    expect(text).toMatch(/joystick/i)
    expect(text).toMatch(/lip button/i)
    // the LED rule, which is not guessable: LED 5's colour says which round of five
    expect(text).toMatch(/1 to 5 light that one LED purple/i)
    expect(text).toMatch(/6 to 9: LED 5 purple plus one more/i)
    expect(text).toMatch(/10 to 14: LED 5 blue plus one more/i)
    expect(text).toMatch(/15 and 16: LED 5 red/i)
    // the worked examples come from the same table as the card and the mode rail
    expect(text).toContain('LED 2 purple and LED 5 purple is file 7')
    expect(text).toContain('LED 2 purple and LED 5 blue is file 12')
    expect(text).toContain('LED 1 purple and LED 5 red is file 16')
    expect(text).not.toMatch(/LED 5 stays on/i)
    w.unmount()
  })

  it('says the drive is only re-read at power-on, and what boot deletes', () => {
    const w = open()
    const text = document.body.textContent ?? ''
    expect(text).toMatch(/only re-reads its drive at power-on/i)
    expect(text).toContain('joystick.bin')
    expect(text).toMatch(/keep backups off the stick/i)
    expect(text).not.toMatch(/reads the list of files/i)
    w.unmount()
  })

  it('ticks off steps with a single click each, and says when all are done', async () => {
    const w = open()
    const boxes = [...document.body.querySelectorAll<HTMLInputElement>('input[type="checkbox"]')]
    expect(boxes.length).toBeGreaterThan(0)
    expect(document.body.textContent).not.toContain("That's everything")
    for (const b of boxes) {
      b.checked = true
      b.dispatchEvent(new Event('change'))
    }
    await w.vm.$nextTick()
    expect(document.body.textContent).toContain("That's everything")
    w.unmount()
  })

  it('can hand the file over again without another API call', async () => {
    const click = vi.fn()
    const orig = document.createElement.bind(document)
    vi.spyOn(document, 'createElement').mockImplementation((tag: string) => {
      const el = orig(tag) as HTMLElement
      if (tag === 'a') el.click = click
      return el
    })
    const w = open()
    const again = [...document.body.querySelectorAll('button')].find((b) =>
      (b.textContent ?? '').includes('Save the file again'),
    )!
    again.click()
    await w.vm.$nextTick()
    expect(click).toHaveBeenCalled()
    w.unmount()
  })

  it('closes on Escape, so it never traps a single-pointer user', async () => {
    const w = open()
    await w.vm.$nextTick() // the dialog attaches its key handler after a tick
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    await w.vm.$nextTick()
    expect(w.emitted('close')).toBeTruthy()
    w.unmount()
  })
})
