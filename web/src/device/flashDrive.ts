// The one sentence for "the catalog does not know this firmware". The library card
// and the editor's settings pane both need it, and they must say the same thing:
// not "hides the drive", not "safe", but that nobody can tell.

/**
 * What to show when `catalog.hidesFlashDrive()` answers `null`. Names the firmware
 * and the emulation mode, because the reader may be looking at a card that shows
 * neither elsewhere.
 */
export function unknownFirmwareWarning(firmware: number, emulationMode: string | number): string {
  return (
    `Firmware ${firmware} is not one this app knows, so it cannot tell whether the ` +
    `flash drive stays visible in emulation mode ${emulationMode}. Keep a known-good ` +
    'profile on the drive before trying it.'
  )
}
