import { describe, expect, it } from 'vitest'
import {
  backupZipName, blobToBase64, filesFromDesktop, filesFromFolderPicker, isSystemPath, planReplace,
  profilesOnDrive, sizeLabel, skippedByTheSwitch,
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

  describe('profilesOnDrive', () => {
    it('puts default.csv first, then the rest in order, lowercased like the device', () => {
      expect(profilesOnDrive(['zelda.csv', 'Fortnite.CSV', 'default.csv', 'apex.csv'])).toEqual([
        'default.csv', 'apex.csv', 'fortnite.csv', 'zelda.csv',
      ])
    })

    it('leaves out prefs.csv, other files, folders and dot-files', () => {
      expect(
        profilesOnDrive([
          'prefs.csv', 'joystick.bin', 'old/backup.csv', '._game.csv', 'notes.txt', 'game.csv',
        ]),
      ).toEqual(['game.csv'])
    })

    it('still numbers the profiles when there is no default.csv', () => {
      expect(profilesOnDrive(['b.csv', 'a.csv'])).toEqual(['a.csv', 'b.csv'])
    })

    it('sorts by plain byte order, as the firmware compares names', () => {
      // digits before letters, one character at a time: 10 comes before 2, and "_"
      // (after the capitals, before the small letters) before "a" once lowercased
      expect(profilesOnDrive(['game2.csv', 'GAME10.csv', 'a.csv', '_X.csv', '1st.csv'])).toEqual([
        '1st.csv', '_x.csv', 'a.csv', 'game10.csv', 'game2.csv',
      ])
    })

    it('leaves out any name holding prefs.csv, as the firmware does, and can say which', () => {
      const drive = ['default.csv', 'MyPrefs.csv', 'prefs.csv', 'old_prefs.csv', 'prefs2.csv']
      expect(profilesOnDrive(drive)).toEqual(['default.csv', 'prefs2.csv'])
      expect(skippedByTheSwitch(drive)).toEqual(['myprefs.csv', 'old_prefs.csv'])
      expect(skippedByTheSwitch(['prefs.csv', 'cod.csv', 'sub/myprefs.csv'])).toEqual([])
    })
  })

  describe('planReplace', () => {
    const drive = ['default.csv', 'cod.csv', 'zelda.csv', 'prefs.csv', 'myprefs.csv', 'joystick.bin']

    it('puts the ticked profiles on in device order and names the ones that go', () => {
      const plan = planReplace(drive, ['Apex.csv', 'default.csv', 'cod.csv'])
      expect(plan).toEqual({
        after: ['default.csv', 'apex.csv', 'cod.csv'],
        removed: ['zelda.csv'],
        keptDefault: false,
        problems: [],
      })
    })

    it("keeps the drive's own default.csv when no ticked profile is one", () => {
      const plan = planReplace(drive, ['apex.csv'])
      expect(plan.after).toEqual(['default.csv', 'apex.csv'])
      expect(plan.keptDefault).toBe(true)
      expect(plan.removed).toEqual(['cod.csv', 'zelda.csv'])
      expect(planReplace(['cod.csv'], ['apex.csv']).keptDefault).toBe(false)
    })

    it('says what stops the write', () => {
      expect(planReplace(drive, []).problems).toEqual(['Tick at least one profile.'])
      expect(planReplace(drive, ['cod.csv', 'COD.csv']).problems[0]).toContain('Two ticked profiles are called cod.csv')
      expect(planReplace(drive, ['old_prefs.csv']).problems[0]).toContain('prefs.csv in its name')
      const many = Array.from({ length: 32 }, (_, i) => `p${i}.csv`)
      expect(planReplace(['x.csv'], many).problems).toEqual([])
      expect(planReplace(drive, many).problems[0]).toContain('33 profiles with default.csv')
    })
  })

  it('turns bytes into base64 for the desktop shell', async () => {
    const bytes = new Uint8Array(70000).map((_, i) => i % 256)
    // a Blob as fetch hands it back (jsdom's own Blob has no arrayBuffer)
    const back = atob(await blobToBase64(await new Response(bytes).blob()))
    expect(back.length).toBe(70000)
    expect([...back.slice(250, 260)].map((c) => c.charCodeAt(0))).toEqual([250, 251, 252, 253, 254, 255, 0, 1, 2, 3])
  })
})
