# What's new

Each release, in plain words. The newest is first. The part for a version is also
shown at the top of its page on GitHub.

## 1.26 — 25 November 2026

### Coming to the Mac App Store

There is now a Mac App Store version of the app. It is the same app, and it is free.
It has been sent to Apple and will be in the store once Apple has checked it.

Apple keeps store apps in a "sandbox": an app may only open the files and drives you
hand it. So the store version works a little differently with the QuadStick:

- **The first time** you plug in the QuadStick, **The device** page says the drive is
  plugged in and asks you to choose it. Press **Choose the drive…**, then **Open**.
  You only do this once.
- After that the app opens the drive by itself, even after you unplug it, plug it back
  in, or restart the Mac.
- Exports and backups are saved in **Downloads › QuadStick exports** (in the download
  version they are in **Documents**).

The version you download from GitHub works as before.

### Smaller things

- On the Mac, **Show in folder**, printing and the message boxes now open through
  macOS itself.
- The NAS version installs again on TerraMaster's TOS 7.

## 1.20 — 24 November 2026

### Put your profiles on the QuadStick, in one step

In the Mac and Windows apps you no longer have to copy files onto the QuadStick by
hand.

Plug in the QuadStick and open **The device** page. Press **Put my profiles on the
QuadStick…**. Tick the profiles you want. The app shows you the new list, numbered in
the QuadStick's own order, with the lights that pick each one. Then press the blue
button, **Back up, then put … on**.

The app saves a backup of the whole drive first. Then it writes your profiles. When it
says **Done**, it is safe to unplug. Unplug the QuadStick and plug it back in, and your
profiles are there.

- Your ticked profiles take the place of the ones on the drive. The old ones stay in
  the backup, so **Restore a backup…** can put them back.
- The QuadStick's own settings (`prefs.csv`) are not touched.
- If you don't tick a `default.csv`, the drive keeps the one it has. That is the
  profile the QuadStick starts with.
- A profile with mistakes can't go on until it is fixed.

This is only in the desktop apps. A web browser, and so the NAS version, can't write
to a USB drive, so there you still export and copy as before.

## 1.16 — 23 November 2026

### A new way to print: the control table

Next to **Print detailed sheets** and **Print summary** there is now **Print control
table**. It is one big table. Every control is down the side, like "Center sip" or
"Chin switch". Every mode is across the top. To see what one control does in every
mode, read along its line. It is handy for someone helping at the chair.

- It prints sideways (landscape), up to six modes to a page.
- Each box shows the button, what it does in the game, and your own note.
- A dash means the control does nothing in that mode.
- At the end, "What the words mean" explains words like *toggle* and *auto-fire*.

The idea comes from QuadStick Config Manager's printed sheet.

### More of your Google Sheet profiles open

Before, one wrong word anywhere in a profile stopped the whole file from opening. Now
the app only stops for a mistake the QuadStick would actually get wrong. For
something the QuadStick just skips, like a word it does not know or a row with no
button, the profile opens with a warning. The warning says what the QuadStick will do,
so you can fix it in the editor.

### Smaller things

- A new mode starts with a way out: side tube sip goes to the next mode, side tube
  puff to the one before.
- The **On the QuadStick** list now leaves out `prefs.csv`, as the QuadStick does,
  and shows the lights for up to 32 profiles.

## 1.13 — 23 November 2026

### Everything about the QuadStick on one page

The **QuadStick backup** box has moved from the Profiles page to the top of **The
device** page, next to the QuadStick's own settings. Backing up and restoring work
just as before.

### See what is on the QuadStick

A new **On the QuadStick** list, under the backup box, shows every profile on the
QuadStick's drive. They are in the order the QuadStick counts them: `default.csv`
first, then A to Z. Next to each is its number and the five status lights that pick
it, coloured just like on the device. To load one: long hard sip on the side tube,
move the joystick until the lights match, then press the lip.

- In the **desktop app** (Mac and Windows) the list is live. Plug the QuadStick in and
  it shows exactly what is on the drive within a few seconds.
- In a browser, or on a NAS, the app cannot see the drive, so the list shows your
  newest backup and says when it was taken.

### Back up with one press in the desktop app

In the desktop app, **Back up the QuadStick** now reads the drive straight away. There
is no folder to pick. The app finds the drive by its name ("Quad Stick" or
"QuadStick") and remembers it. If your drive has another name, press **Choose the
drive…** once and the app remembers that one. The app only ever reads the drive. It
never changes anything on it.

## 1.11 — 22 November 2026

### Test your QuadStick

A new **Test it** page. Plug the QuadStick in, and every sip, puff, lip press and
joystick move lights up on a photo of the device the moment it happens. Blue-green
is a sip, orange is a puff, pale means soft. The lights show which mode it is in.

Press **Start the test** and it walks you through every tube, one at a time: "hard
sip on the left tube". A yellow ring shows where. Then it shows ✓ or ✗ and what the
QuadStick really felt, so "asked for hard, got soft" is easy to spot. If you miss,
just try again; there is nothing to click first. It is good for practice too.

- It needs a small test profile, `qstest.csv`. The page gives it to you, with the
  steps to copy it onto the QuadStick.
- It needs **Chrome or Edge** on the computer the QuadStick is plugged into. In the
  desktop app, press **Open the tester in your browser**. On a NAS, use the app's
  `https://` address.
- It only listens. It never changes anything on the QuadStick.

### Back up the QuadStick

A new **QuadStick backup** box on the Profiles page. Press **Back up the QuadStick**,
pick its drive, and every file on it is saved in the app with the date and time.

To put it back, press **Restore a backup…**, pick the date, and save it as one
`.zip`. Copy the files inside onto the QuadStick, unplug it and plug it back in. The
app shows each step.

### Fixes

- **Mode names.** A mode is now always saved to the QuadStick under the name you see
  in the editor. Before, a Google Sheet whose tabs were copied and renamed could
  export every mode under the old name.
- **Security.** The NAS and Docker version now runs the latest stable nginx web
  server, and every NAS update fetches the newest security patches.

## 1.1 and earlier

The first releases: the profile library, the photo-based editor, checks before
export, PlayStation ↔ Xbox conversion, printing, the device's own settings, and the
"How it works" pages. The README shows them all.
