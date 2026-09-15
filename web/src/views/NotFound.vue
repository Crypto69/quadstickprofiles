<script setup lang="ts">
import { RouterLink } from 'vue-router'
</script>

<template>
  <section class="card pad">
    <h1>Not found</h1>
    <p>That page does not exist.</p>
    <RouterLink class="btn" to="/">Back to the library</RouterLink>
  </section>
</template>

<style scoped>
.pad {
  padding: var(--sp-5);
}
</style>
