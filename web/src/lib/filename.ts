/**
 * The one rule for "what should this profile's file on the QuadStick be called?".
 *
 * It exists to auto-fill the filename box from the name the user has just typed, so
 * that naming a copy once is enough and the pair matches for free. The two are never
 * forced to agree afterwards: the firmware never reads the name, so "Fortnite - Dad's
 * build" beside `ddfortnite.csv` is a perfectly good label, not a fault. Nothing here
 * compares the two or complains about them.
 *
 * This must agree, character for character, with `csv_filename_for_name` in
 * `core/qsprofile/catalog.py` — that is the source of truth, and the API applies the
 * same rule server-side. Change one, change both.
 */

/** The device's limit on a profile filename, as `catalog.MAX_CSV_FILENAME_CHARS`. */
export const MAX_CSV_FILENAME_CHARS = 31

/** How many characters of stem fit once `.csv` is accounted for. */
const STEM_BUDGET = MAX_CSV_FILENAME_CHARS - '.csv'.length

/**
 * The `.csv` filename a profile called `name` should have: lowercase, only
 * `[a-z0-9_-]`, any run of anything else collapsed to a single `_`, no leading or
 * trailing `._-`, the stem cut to fit the device's 31 characters, and `profile.csv`
 * when nothing survives.
 *
 * Underscores and dashes are **kept**. The filename rules allow both, so stripping
 * them — as this view's old `slug()` did, turning `cod_ww2` into `codww2.csv` —
 * invented a different name for the same profile.
 */
export function csvFilenameForName(name: string): string {
  const collapsed = String(name ?? '')
    .toLowerCase()
    .replace(/[^a-z0-9_-]+/g, '_')
  // Strip first, then cut: the Python rule does the same, and cutting first would let
  // a leading run of separators eat into the budget.
  const stem = trimEnds(collapsed).slice(0, STEM_BUDGET).replace(/[._-]+$/, '')
  return `${stem || 'profile'}.csv`
}

/** `str.strip('._-')` — both ends, any mix of those three. */
function trimEnds(s: string): string {
  return s.replace(/^[._-]+/, '').replace(/[._-]+$/, '')
}

/**
 * A default name for a copy: `cvcodww2` → `cvcodww2_copy`. Chosen so that the
 * filename this suggests (`cvcodww2_copy.csv`) is what the API would have invented
 * anyway, and so pressing Enter straight away gives a matching pair.
 */
export function copyName(name: string): string {
  return `${name.trim() || 'profile'}_copy`
}

/** The same, for a conversion: `cvcodww2` → `cvcodww2_xbox` / `cvcodww2_ps`. */
export function convertedName(name: string, target: 'playstation' | 'xbox'): string {
  return `${name.trim() || 'profile'}_${target === 'xbox' ? 'xbox' : 'ps'}`
}
