<script setup lang="ts">
// The Learn index: nine short topics, each its own page so a link can point at one.
import { RouterLink } from 'vue-router'
import { TOPICS } from '@/learn/topics'
</script>

<template>
  <div class="stack">
    <header>
      <h1>How the QuadStick works</h1>
      <p class="lede">
        Nine short pages. No setting up, nothing to plug in — just what the parts do and
        why profiles are built the way they are.
      </p>
    </header>

    <ol class="topics">
      <li v-for="(t, i) in TOPICS" :key="t.slug">
        <RouterLink :to="`/learn/${t.slug}`">
          <span class="num">{{ i + 1 }}</span>
          <span>
            <b>{{ t.title }}</b>
            <small>{{ t.blurb }}</small>
          </span>
        </RouterLink>
      </li>
    </ol>
  </div>
</template>

<style scoped>
.lede {
  font-size: var(--text-lg);
  color: var(--ink-soft);
  max-width: 42rem;
}

.topics {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(300px, 100%), 1fr));
  gap: var(--sp-3);
}

.topics a {
  display: flex;
  align-items: flex-start;
  gap: var(--sp-3);
  min-height: var(--target);
  padding: var(--sp-3);
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  background: var(--paper);
  color: var(--ink);
  text-decoration: none;
  height: 100%;
}
.topics a:hover {
  border-color: var(--mode);
}

.num {
  flex: none;
  width: 30px;
  height: 30px;
  border-radius: 50%;
  background: var(--mode-soft);
  color: var(--mode);
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: var(--text-sm);
}

.topics b {
  display: block;
}
.topics small {
  color: var(--ink-soft);
  font-size: var(--text-sm);
}
</style>
