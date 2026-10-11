import { createRouter, createWebHistory } from 'vue-router';
import { handleHotUpdate, routes } from 'vue-router/auto-routes';

import { loggedInBots } from '@/composables/loginInfo';
import { initBots, useBotStore } from '@/stores/ftbotwrapper';

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
});

// Guest home: the read-only showcase is the only workspace page a visitor
// without a configured bot may reach.
const SHOWCASE_PATH = '/showcase';

router.beforeEach((to) => {
  const botStore = useBotStore();

  // Only initialise the bot stores when the visitor actually has stored
  // logins. Guests must never trigger authenticated requests (they would only
  // produce 401s), so `initBots()` stays out of the guest path.
  if (Object.keys(loggedInBots.value).length > 0) {
    initBots();
  }

  if (botStore.hasBots) {
    // Logged-in behaviour is unchanged.
    return true;
  }

  // Guest: the dashboard FIRST SCREEN (read-only showcase) is the home page a
  // shared link must land on. Only the login form stays reachable next to it so
  // the owner can still sign in from a shared link; every other route - the
  // marketing landing page and all workspace pages - resolves to the showcase.
  if (to.path === SHOWCASE_PATH || to.path === '/login') {
    return true;
  }
  return { path: SHOWCASE_PATH };
});

if (import.meta.hot) {
  handleHotUpdate(router);
}

export default router;
