/// <reference types="vite/client" />
declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<{}, {}, any>
  export default component
}

/** The deploy number from deploy.sh (e.g. "1.3"), injected at build time; "dev" locally. */
declare const __APP_VERSION__: string
