import { describe, expect, it } from 'vitest'
import {
  backupZipName, filesFromDesktop, filesFromFolderPicker, isSystemPath, sizeLabel,
} from './driveFiles'

function picked(relativePath: string, body = 'x'): File {
  const f = new File([body], relativePath.split('/').pop()!)
  Object.defineProperty(f, 'webkitRelativePath', { value: relativePath })
  return f
}

describe('driveFiles', () => {
  it('drops the picked folder name so paths start at the top of the drive', () => {
    const out = filesFromFolderPicker([picked('QUADSTICK/default.csv'), picked('QUADSTICK/old/cod.csv')])
    expect(out.map((f) => f.path)).toEqual(['default.csv', 'old/cod.csv'])
  })

  it('leaves out what a computer writes on a removable drive', () => {
    const out = filesFromFolderPicker([
      picked('QUADSTICK/default.csv'),
      picked('QUADSTICK/._default.csv'),
      picked('QUADSTICK/.Spotlight-V100/Store-V2/index'),
      picked('QUADSTICK/System Volume Information/IndexerVolumeGuid'),
      picked('QUADSTICK/$RECYCLE.BIN/desktop.ini'),
    ])
    expect(out.map((f) => f.path)).toEqual(['default.csv'])
    expect(isSystemPath('joystick.bin')).toBe(false)
  })

  it('turns the desktop shell’s base64 back into the same bytes', async () => {
    const f = filesFromDesktop([{ path: 'joystick.bin', data: btoa('\x00\x01\xff') }])[0]!
    expect(f.path).toBe('joystick.bin')
    // jsdom's Blob has no arrayBuffer(); FileReader is what it does have
    const buf = await new Promise<ArrayBuffer>((resolve) => {
      const r = new FileReader()
      r.onload = () => resolve(r.result as ArrayBuffer)
      r.readAsArrayBuffer(f.data)
    })
    expect([...new Uint8Array(buf)]).toEqual([0, 1, 255])
  })

  it('names the zip in local time, the time the list shows', () => {
    expect(backupZipName(new Date(2026, 10, 2, 9, 5))).toBe('quadstick-backup-2026-11-02-0905.zip')
  })

  it('says sizes in words a person reads', () => {
    expect(sizeLabel(900)).toBe('900 bytes')
    expect(sizeLabel(1536)).toBe('1.5 KB')
  })
})
