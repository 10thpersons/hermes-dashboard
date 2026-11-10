// Keep this policy identical to backend/config.py. Never substitute key material.
export function dashboardKey(): string | null {
  const key = process.env.DASHBOARD_API_KEY;
  // Require at least 32 printable ASCII characters, no whitespace, and some variety.
  // Operators must generate a random key; validation cannot prove entropy.
  return key && key.length >= 32 && !/[^\x21-\x7e]/.test(key) && new Set(key).size >= 8
    ? key
    : null;
}
