export const NOTIFICATION_PREFERENCES_STORAGE_KEY = "creatorpulse.notificationPreferences.v1";

export function applyNotificationPreferenceState(rules, storedState) {
  if (!storedState || typeof storedState !== "object") {
    return rules;
  }

  return rules.map((rule) => {
    if (typeof storedState[rule.id] !== "boolean") {
      return rule;
    }

    return { ...rule, enabled: storedState[rule.id] };
  });
}

export function serializeNotificationPreferenceState(rules) {
  return rules.reduce((state, rule) => {
    state[rule.id] = Boolean(rule.enabled);
    return state;
  }, {});
}

export function loadNotificationPreferenceState(storage = globalThis.localStorage) {
  if (!storage) {
    return {};
  }

  try {
    const raw = storage.getItem(NOTIFICATION_PREFERENCES_STORAGE_KEY);
    if (!raw) {
      return {};
    }

    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

export function saveNotificationPreferenceState(rules, storage = globalThis.localStorage) {
  if (!storage) {
    return;
  }

  storage.setItem(
    NOTIFICATION_PREFERENCES_STORAGE_KEY,
    JSON.stringify(serializeNotificationPreferenceState(rules))
  );
}
