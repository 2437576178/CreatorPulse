async function request(path) {
  const response = await fetch(path, { credentials: "include" });
  const payload = await response.json();

  if (!response.ok) {
    const message = payload?.error?.message || "API request failed";
    throw new Error(message);
  }

  return payload;
}

export function login(email, password) {
  return fetch("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ email, password })
  }).then(async (response) => {
    const payload = await response.json();
    if (!response.ok) {
      const message = payload?.error?.message || "Login failed";
      throw new Error(message);
    }
    return payload;
  });
}

export function registerAccount({ email, password, displayName, platforms }) {
  return fetch("/api/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ email, password, displayName, platforms })
  }).then(async (response) => {
    const payload = await response.json();
    if (!response.ok) {
      const message = payload?.error?.message || "Register failed";
      throw new Error(message);
    }
    return payload;
  });
}

export function logout() {
  return fetch("/api/auth/logout", { method: "POST", credentials: "include" }).then(async (response) => {
    const payload = await response.json();
    if (!response.ok) {
      const message = payload?.error?.message || "Logout failed";
      throw new Error(message);
    }
    return payload;
  });
}

export function fetchMe() {
  return request("/api/me");
}

export function fetchGrowthDashboard() {
  return request("/api/me/dashboard/growth");
}

export function fetchFansAnalysis() {
  return request("/api/me/fans");
}

export function fetchVideoAnalysis() {
  return request("/api/me/videos");
}

export function fetchContentDistribution() {
  return request("/api/me/distribution");
}

export function fetchOpportunities() {
  return request("/api/me/opportunities");
}

export function fetchProfile() {
  return request("/api/me/profile");
}

export function fetchSimulationStatus() {
  return request("/api/admin/simulation/status");
}

export function fetchSimulationCreators() {
  return request("/api/admin/simulation/creators");
}

export function fetchSimulationEvents(limit = 30) {
  return request(`/api/admin/simulation/events?limit=${limit}`);
}
