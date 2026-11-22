# What's new

Each release, in plain words. The newest is first. The part for a version is also
shown at the top of its page on GitHub.

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
