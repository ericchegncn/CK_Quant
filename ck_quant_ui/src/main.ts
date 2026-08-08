import { createPinia } from 'pinia';
import piniaPluginPersistedstate from 'pinia-plugin-persistedstate';
import ui from '@nuxt/ui/vue-plugin';
import { App as CapacitorApp } from '@capacitor/app';

import { initializeNativeAuthStorage, isNativeApp } from './services/nativeSecureStorage';
import './styles/tailwind.css';

async function bootstrap() {
  await initializeNativeAuthStorage();
  const [{ default: App }, { i18n }, { VueDraggableGrid }, { default: router }] = await Promise.all(
    [
      import('./App.vue'),
      import('./i18n'),
      import('./plugins/vue-grid-layout'),
      import('./router'),
    ],
  );

  const myApp = createApp(App);
  const pinia = createPinia();
  pinia.use(piniaPluginPersistedstate);
  myApp.use(pinia);

  myApp.use(ui);
  myApp.use(i18n);

  myApp.use(router);
  myApp.use(VueDraggableGrid);

  myApp.mount('#app');

  if (isNativeApp()) {
    await CapacitorApp.addListener('backButton', ({ canGoBack }) => {
      if (canGoBack) window.history.back();
      else void CapacitorApp.exitApp();
    });
  }
}

void bootstrap();
