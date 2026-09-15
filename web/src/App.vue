<script setup lang="ts">
import { onMounted } from 'vue'
import { RouterLink, RouterView } from 'vue-router'
import { useCatalogStore } from '@/stores/catalog'
import logoMark from '@/assets/logo-mark.png'

const catalog = useCatalogStore()
const appVersion = __APP_VERSION__

// The catalog gates every keyword the UI can offer, so it loads before anything else.
onMounted(() => {
  catalog.load().catch(() => {
    /* the banner below reports it; the views handle the empty catalog */
  })
})
</script>

<template>
  <a class="skip-link sr-only" href="#main">Skip to main content</a>

  <header class="top">
    <RouterLink to="/" class="brand">
      <!-- the emblem from the logo; the name next to it is the accessible text -->
      <img class="brand__mark" :src="logoMark" alt="" width="44" height="44" />
      <span class="brand__name">QuadStick <span>Profile Studio</span></span>
    </RouterLink>
    <nav aria-label="Main">
      <RouterLink to="/">Profiles</RouterLink>
      <RouterLink to="/device">The device</RouterLink>
      <RouterLink to="/learn">How it works</RouterLink>
    </nav>
    <div class="spacer" />
    <p v-if="catalog.loading" class="hint" role="status">Loading the keyword catalog…</p>
    <span class="version" title="Deployed version">v{{ appVersion }}</span>
  </header>

  <p v-if="catalog.error" class="banner banner--error" role="alert">
    Could not reach the API: {{ catalog.error }}
    <button class="btn btn--small" type="button" @click="catalog.load(true)">Try again</button>
  </p>

  <main id="main">
    <RouterView />
  </main>
</template>

<style scoped>
.top {
  display: flex;
  align-items: center;
  gap: var(--sp-4);
  padding: var(--sp-3) var(--sp-5);
  background: var(--paper);
  border-bottom: 1px solid var(--line);
}

.brand {
  display: inline-flex;
  align-items: center;
  gap: var(--sp-2);
  min-height: var(--target);
  font-size: var(--text-lg);
  font-weight: 700;
  color: var(--ink);
  text-decoration: none;
  letter-spacing: -0.01em;
}
.brand__mark {
  width: 44px;
  height: 44px;
  flex: none;
}
.brand__name span {
  font-weight: 400;
  color: var(--ink-soft);
}

nav {
  display: flex;
  gap: var(--sp-1);
}
nav a {
  display: inline-flex;
  align-items: center;
  min-height: var(--target);
  padding: 0 var(--sp-3);
  border-radius: var(--radius);
  color: var(--ink-soft);
  font-weight: 600;
  font-size: var(--text-sm);
  text-decoration: none;
}
nav a:hover {
  background: var(--paper-sunk);
  color: var(--ink);
}
/* exact on the library so it is not lit while a profile is open */
nav a.router-link-exact-active {
  background: var(--mode-soft);
  color: var(--mode);
}

.version {
  font-size: var(--text-sm);
  font-variant-numeric: tabular-nums;
  color: var(--ink-soft);
  white-space: nowrap;
}

.banner {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  margin: 0;
  padding: var(--sp-3) var(--sp-5);
  font-size: var(--text-sm);
}
.banner--error {
  background: var(--error-soft);
  color: var(--error);
  border-bottom: 1px solid var(--error);
}

main {
  max-width: 1180px;
  margin: 0 auto;
  padding: var(--sp-5);
}
</style>
