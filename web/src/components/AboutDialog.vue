<script setup lang="ts">
// What this app is and why it was written, plus where to find the rest of the
// accessibility work. The text follows the top of README.md; keep them in step.
import ModalDialog from './ModalDialog.vue'

defineProps<{ open: boolean }>()
const emit = defineEmits<{ close: [] }>()

const appVersion = __APP_VERSION__

// Icons are inline paths on a 24×24 grid: the app is offline, so nothing is
// fetched from an icon CDN and no font is pulled in for four glyphs.
const links = [
  {
    label: 'myaccessibility.ai',
    href: 'https://myaccessibility.ai',
    // globe
    icon: 'M12 2a10 10 0 100 20 10 10 0 000-20zm0 0c2.5 2.7 3.8 6.3 3.8 10S14.5 19.3 12 22m0-20C9.5 4.7 8.2 8.3 8.2 12S9.5 19.3 12 22M2.5 9h19M2.5 15h19',
  },
  {
    label: 'YouTube',
    href: 'https://www.youtube.com/@myaccessibility',
    // rounded screen with a play triangle
    icon: 'M3 8.5A2.5 2.5 0 015.5 6h13A2.5 2.5 0 0121 8.5v7a2.5 2.5 0 01-2.5 2.5h-13A2.5 2.5 0 013 15.5v-7zM10.2 9.4l4.6 2.6-4.6 2.6V9.4z',
  },
  {
    label: 'Instagram',
    href: 'https://www.instagram.com/myaccessibility',
    // rounded square, lens, flash dot
    icon: 'M7.5 3.5h9a4 4 0 014 4v9a4 4 0 01-4 4h-9a4 4 0 01-4-4v-9a4 4 0 014-4zM12 8.2a3.8 3.8 0 100 7.6 3.8 3.8 0 000-7.6zM17.1 6.6v.01',
  },
  {
    label: 'LinkedIn',
    href: 'https://www.linkedin.com/in/chris-venter/',
    // card with the "in" strokes
    icon: 'M4 3.5h16a.5.5 0 01.5.5v16a.5.5 0 01-.5.5H4a.5.5 0 01-.5-.5V4a.5.5 0 01.5-.5zM7.6 10.3v6.4M7.6 7.5v.01M11.6 16.7v-6.4M11.6 12.8c0-1.4 1-2.5 2.4-2.5s2.4 1.1 2.4 2.5v3.9',
  },
]
</script>

<template>
  <ModalDialog :open="open" title="About QuadStick Profile Studio" @close="emit('close')">
    <div class="about">
      <p class="version">Version {{ appVersion }}</p>

      <p>
        An application for QuadStick game profiles: read them, check them against what
        the device will actually accept, convert between PlayStation and Xbox button names,
        and print a reference card. Everything runs on your own machine — nothing is
        uploaded anywhere. Copying the <code>.csv</code> onto the QuadStick's flash drive
        stays manual on purpose, and the app walks you through it.
      </p>

      <h3>Why I built this</h3>
      <p>
        I received my QuadStick with the amazing help of David Nelson from
        <a href="http://www.innovativeat.com.au/" target="_blank" rel="noopener noreferrer"
          >innovativeat.com.au</a
        >, who helps supply adaptive gaming equipment to people across Australia. Getting my
        head around how it worked, including how profiles and modes worked, was quite
        difficult at first.
      </p>
      <p>
        I started playing with the profiles but that spreadsheet was driving me crazy. It
        just wasn't clear enough, so I figured I needed to teach myself how the whole thing
        worked. I built myself an app that lets me configure things much faster now, and
        taught myself a lot more about how it all works along the way.
      </p>
      <p>
        Hopefully it helps you too. If it does, drop me a message — I'm very open to
        feedback and changes, so let me know if there's something else you want.
      </p>

      <h3>More from MyAccessibility.ai</h3>
      <p>
        A nonprofit making free accessibility software, 3D print files and resources for
        people with spinal cord injuries and disabilities.
      </p>
      <ul class="links">
        <li v-for="link in links" :key="link.href">
          <a class="btn btn--quiet" :href="link.href" target="_blank" rel="noopener noreferrer">
            <!-- decorative: the label beside it already names the destination -->
            <svg class="icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
              <path :d="link.icon" />
            </svg>
            {{ link.label }}
          </a>
        </li>
      </ul>

      <p class="foot">
        Questions or feedback:
        <a href="mailto:support@myaccessibility.ai">support@myaccessibility.ai</a>
      </p>
    </div>
  </ModalDialog>
</template>

<style scoped>
.about p {
  margin: 0 0 var(--sp-3);
  line-height: 1.55;
}
.version {
  color: var(--ink-soft);
  font-variant-numeric: tabular-nums;
}
h3 {
  margin: var(--sp-4) 0 var(--sp-2);
  font-size: var(--text-md, 1rem);
}
.links {
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-2);
  margin: 0 0 var(--sp-3);
  padding: 0;
  list-style: none;
}
.links a {
  display: inline-flex;
  align-items: center;
  gap: var(--sp-2);
  min-height: var(--target);
}
.icon {
  width: 18px;
  height: 18px;
  flex: none;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.7;
  stroke-linecap: round;
  stroke-linejoin: round;
}
.foot {
  margin-bottom: 0;
  color: var(--ink-soft);
  font-size: var(--text-sm);
}
</style>
