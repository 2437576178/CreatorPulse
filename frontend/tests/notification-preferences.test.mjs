import assert from "node:assert/strict";
import test from "node:test";
import {
  applyNotificationPreferenceState,
  loadNotificationPreferenceState,
  NOTIFICATION_PREFERENCES_STORAGE_KEY,
  saveNotificationPreferenceState
} from "../src/utils/notificationPreferences.js";

function createMemoryStorage(initial = {}) {
  const store = new Map(Object.entries(initial));
  return {
    getItem(key) {
      return store.has(key) ? store.get(key) : null;
    },
    setItem(key, value) {
      store.set(key, String(value));
    }
  };
}

test("saves notification rule enabled state by rule id", () => {
  const storage = createMemoryStorage();
  const rules = [
    { id: "growth", enabled: false },
    { id: "traffic", enabled: true }
  ];

  saveNotificationPreferenceState(rules, storage);

  assert.deepEqual(JSON.parse(storage.getItem(NOTIFICATION_PREFERENCES_STORAGE_KEY)), {
    growth: false,
    traffic: true
  });
});

test("loads saved notification rule state from storage", () => {
  const storage = createMemoryStorage({
    [NOTIFICATION_PREFERENCES_STORAGE_KEY]: JSON.stringify({ growth: false, traffic: true })
  });

  assert.deepEqual(loadNotificationPreferenceState(storage), {
    growth: false,
    traffic: true
  });
});

test("applies saved notification state without dropping new rules", () => {
  const rules = [
    { id: "growth", enabled: true },
    { id: "traffic", enabled: true },
    { id: "negativeComment", enabled: true }
  ];

  assert.deepEqual(applyNotificationPreferenceState(rules, { growth: false, traffic: true }), [
    { id: "growth", enabled: false },
    { id: "traffic", enabled: true },
    { id: "negativeComment", enabled: true }
  ]);
});
