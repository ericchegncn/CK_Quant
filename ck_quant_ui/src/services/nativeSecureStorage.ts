import { Capacitor, registerPlugin } from '@capacitor/core';

const AUTH_STORAGE_KEY = 'ftAuthLoginInfo';

interface SecureStoragePlugin {
  get(options: { key: string }): Promise<{ value: string | null }>;
  set(options: { key: string; value: string }): Promise<void>;
  remove(options: { key: string }): Promise<void>;
}

const SecureStorage = registerPlugin<SecureStoragePlugin>('SecureStorage');
let secureWriteQueue: Promise<void> = Promise.resolve();

export function isNativeApp() {
  return Capacitor.isNativePlatform();
}

export async function initializeNativeAuthStorage() {
  if (!isNativeApp()) return;
  try {
    const { value } = await SecureStorage.get({ key: AUTH_STORAGE_KEY });
    if (value) sessionStorage.setItem(AUTH_STORAGE_KEY, value);
  } catch (error) {
    console.error('Unable to restore encrypted login session.', error);
  }
}

export function persistNativeAuthStorage(value: string) {
  if (!isNativeApp()) return Promise.resolve();
  secureWriteQueue = secureWriteQueue
    .catch(() => undefined)
    .then(async () => {
      if (value === '{}') {
        await SecureStorage.remove({ key: AUTH_STORAGE_KEY });
      } else {
        await SecureStorage.set({ key: AUTH_STORAGE_KEY, value });
      }
    });
  return secureWriteQueue.catch((error) => {
    console.error('Unable to persist encrypted login session.', error);
  });
}
