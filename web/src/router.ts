import { createRouter, createWebHistory } from 'vue-router'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'library', component: () => import('@/views/LibraryView.vue') },
    {
      path: '/profiles/:id',
      name: 'profile',
      component: () => import('@/views/EditorView.vue'),
      props: true,
    },
    {
      path: '/device',
      name: 'device',
      component: () => import('@/views/DeviceSettingsView.vue'),
    },
    { path: '/learn', name: 'learn', component: () => import('@/views/LearnView.vue') },
    {
      path: '/learn/:slug',
      name: 'learn-topic',
      component: () => import('@/views/LearnTopicView.vue'),
      props: true,
    },
    { path: '/:pathMatch(.*)*', name: 'not-found', component: () => import('@/views/NotFound.vue') },
  ],
  scrollBehavior: () => ({ top: 0 }),
})
