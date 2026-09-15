# QuadStick hardware reference (from the user manual; screenshots in manual-screenshots/)

Use this for the Learn section and the printed card. Draw our own diagrams
from it; the screenshots are the manufacturer's and are kept here for reference.

## Front
1. **Status LEDs** — five blue/red LEDs: sensor activation, active
   configuration profile, boot/self-test, USB status.
2. **Mouthpiece** — three sip/puff tubes (analog pressure sensors) on the
   joystick; moving the whole head is the joystick's XY motion.
3. **Lip Button** — round black disc below the mouthpiece; the lip position
   sensor, adjustable sensitivity and position. Pressed with the lip or chin.
   Profile input name: `lip` (and `lip_soft`). The owner calls theirs a chin switch;
   the card lets a profile name it (`actions["inputs"]["lip"]`).
4. **Input/Output LEDs** — four green LEDs: output status 1–4 top to bottom,
   or input status 1–2 (and 7–8 if the top jack is an input jack) bottom to top.
5. **Side tube** — the mode selector sip/puff tube. Profile inputs
   `right_sip`, `right_puff` (+ `_soft`).

## Back panel jacks and the `digital_in_*` numbering
| jack | profile inputs | notes |
|---|---|---|
| Bottom 3.5 mm "In" | `digital_in_1`, `digital_in_2` | ability-switch inputs; also a 3.3 V TTL serial port |
| USB-A | `digital_in_3`, `digital_in_4` | primarily for daisy-chained gamepads (UltraStik 360, Mayflash F300, DualShock 4); D−/D+ can act as inputs 3–4 |
| Centre 3.5 mm "Lip" | `lip`, plus auxiliary `digital_in_5`, `digital_in_6` | the lip button plugs in here |
| Top 3.5 mm "Out" or "In 7-8" | `digital_in_7`, `digital_in_8` **or** relay outputs `digital_out1/2` | chosen at purchase. **The owner's unit is labelled `In 7-8`** — legible in `images/rear.png` — so on that device it is an input jack, and `digital_out1/2` are not available |
| USB-B | — | power/data to the console or PC |

`catalog.DIGITAL_JACKS` carries this table so the card can print which jack a
switch lives on. Note the numbering: the top jack is 7–8, not 3–4.

`images/rear.png` is the authority for the labels, and they read, top to bottom on
the left: **In 7-8**, **Lip 5-6**, **In 1-2**, with **In 3-4** beside the USB-A
socket on the right. The editor's device view draws its callouts from that photo.
