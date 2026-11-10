// Only nginx may reach the frontend: it overwrites this header with $remote_addr.
// Missing identity uses one conservative bucket, never a fresh caller-selected key.
export function loginIdentity(headers) {
  return headers.get('x-dashboard-client-ip')?.trim() || 'unattributed';
}

export function createLoginLimiter(now = Date.now, maxBuckets = 4096) {
  const attempts = new Map();
  const windowMs = 60000;
  const lockoutMs = 30000;
  function check(identity) {
    const time = now();
    for (const [key, record] of attempts) {
      const expiry = record.count >= 5 ? lockoutMs : windowMs;
      if (time - record.lastAttempt >= expiry) attempts.delete(key);
    }
    const record = attempts.get(identity);
    if (record?.count >= 5) {
      return { allowed: false, retryAfter: Math.ceil((lockoutMs - (time - record.lastAttempt)) / 1000) };
    }
    // Do not evict active buckets: capacity exhaustion must not reset a lockout.
    if (!record && attempts.size >= maxBuckets) return { allowed: false, retryAfter: 30 };
    return { allowed: true };
  }
  function fail(identity) {
    const record = attempts.get(identity);
    if (record) {
      record.count++;
      record.lastAttempt = now();
    } else if (attempts.size < maxBuckets) {
      attempts.set(identity, { count: 1, lastAttempt: now() });
    }
  }
  return { check, fail, clear: (identity) => attempts.delete(identity) };
}
