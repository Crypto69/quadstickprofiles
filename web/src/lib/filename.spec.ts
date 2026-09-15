import { describe, expect, it } from 'vitest'
import { MAX_CSV_FILENAME_CHARS, convertedName, copyName, csvFilenameForName } from './filename'

/**
 * These cases are pinned against `csv_filename_for_name` in
 * `core/qsprofile/catalog.py`, which is the source of truth and is applied
 * server-side too. Every expectation here was produced by running that function.
 * If one of these ever disagrees, the two rules have drifted and the UI will start
 * suggesting a filename the API would not.
 */
describe('csvFilenameForName', () => {
  it.each([
    // the owner's own case: the copy's name and file finally agree
    ['cvcodww2', 'cvcodww2.csv'],
    ['cvcodww2_copy', 'cvcodww2_copy.csv'],
    ['cvcodww2 (copy)', 'cvcodww2_copy.csv'],

    // underscores and dashes SURVIVE. The old slug() stripped them, so `cod_ww2`
    // became `codww2.csv` — a different file from the one on the stick.
    ['cod_ww2', 'cod_ww2.csv'],
    ['cod-ww2', 'cod-ww2.csv'],

    // a run of anything else collapses to one underscore, not one per character
    ['Call of Duty: WW2', 'call_of_duty_ww2.csv'],
    ['MiXeD CaSe 99', 'mixed_case_99.csv'],
    ['a!!!b', 'a_b.csv'],
    ['name.with.dots', 'name_with_dots.csv'],
    ['a/b\\c', 'a_b_c.csv'],
    ['Café Noir', 'caf_noir.csv'],

    // lowercased, and the ends trimmed of . _ -
    ['Fortnite', 'fortnite.csv'],
    ['  Fortnite  ', 'fortnite.csv'],
    ['_leading', 'leading.csv'],
    ['trailing_', 'trailing.csv'],
    ['_a_', 'a.csv'],
    ['-a-', 'a.csv'],
    ['._-x-_.', 'x.csv'],

    // nothing survives → a name that at least loads
    ['', 'profile.csv'],
    ['   ', 'profile.csv'],
    ['___', 'profile.csv'],
    ['...', 'profile.csv'],
    ['--', 'profile.csv'],
    ['!!!', 'profile.csv'],
    ['日本語', 'profile.csv'],

    // the stem is cut to 27, so the whole filename fits the device's 31
    ['A'.repeat(40), `${'a'.repeat(27)}.csv`],
    ['abcdefghijklmnopqrstuvwxy_z', 'abcdefghijklmnopqrstuvwxy_z.csv'],
    ['abcdefghijklmnopqrstuvwxyz_qq', 'abcdefghijklmnopqrstuvwxyz.csv'],
    ['0123456789012345678901234567890', '012345678901234567890123456.csv'],
    // the cut lands on the separator, which is then trimmed rather than left dangling
    [`${'x'.repeat(26)}   y`, `${'x'.repeat(26)}.csv`],
  ])('%j → %j', (name, expected) => {
    expect(csvFilenameForName(name)).toBe(expected)
  })

  it('never produces a filename longer than the device allows', () => {
    for (const name of ['A'.repeat(200), 'a b c '.repeat(40), '_'.repeat(50) + 'z'.repeat(50)]) {
      expect(csvFilenameForName(name).length).toBeLessThanOrEqual(MAX_CSV_FILENAME_CHARS)
    }
  })

  it('always produces something the filename rules accept', () => {
    for (const name of ['Call of Duty: WW2', '', '日本語', '._-x-_.', 'A'.repeat(40)]) {
      expect(csvFilenameForName(name)).toMatch(/^[a-z0-9][a-z0-9_.-]*\.csv$/)
    }
  })
})

describe('the suggested names', () => {
  it('names a copy so its filename matches without any typing', () => {
    expect(copyName('cvcodww2')).toBe('cvcodww2_copy')
    expect(csvFilenameForName(copyName('cvcodww2'))).toBe('cvcodww2_copy.csv')
  })

  it('names a conversion after the naming set it produces', () => {
    expect(convertedName('cvcodww2', 'xbox')).toBe('cvcodww2_xbox')
    expect(convertedName('cvcodww2', 'playstation')).toBe('cvcodww2_ps')
    expect(csvFilenameForName(convertedName('cvcodww2', 'xbox'))).toBe('cvcodww2_xbox.csv')
  })

  it('falls back rather than producing a bare suffix', () => {
    expect(copyName('  ')).toBe('profile_copy')
    expect(convertedName('', 'xbox')).toBe('profile_xbox')
  })
})
