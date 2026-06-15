const CREATOR_ID = "demo";

async function request(path) {
  const response = await fetch(path);
  const payload = await response.json();

  if (!response.ok) {
    const message = payload?.error?.message || "API request failed";
    throw new Error(message);
  }

  return payload;
}

export function fetchGrowthDashboard() {
  return request(`/api/creators/${CREATOR_ID}/dashboard/growth`);
}

export function fetchFansAnalysis() {
  return request(`/api/creators/${CREATOR_ID}/fans`);
}
