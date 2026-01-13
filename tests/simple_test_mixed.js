import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  scenarios: {
    basic_client: {
      executor: 'constant-vus',
      vus: 1,
      duration: '30s',
      exec: 'basicClient',
    },
    pro_client: {
      executor: 'constant-vus',
      vus: 1,
      duration: '30s',
      exec: 'proClient',
    },
  },
};

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';

export function basicClient() {
  const payload = JSON.stringify({
    message: 'Test query for basic',
    top_k: 2
  });

  const res = http.post(`${BASE_URL}/agent/query`, payload, {
    headers: {
      'Content-Type': 'application/json',
      'X-Client-ID': 'basic-mixed-001',
    },
  });

  console.log(`[BASIC] Status: ${res.status}`);

  check(res, {
    'basic - is 200 or 429': (r) => r.status === 200 || r.status === 429,
  });
  if (res.status === 429) {
    console.log(`  ⚠ RATE LIMITED - Retry after ${res.headers['Retry-After']}s`);
  }
  sleep(0.5);  // 12 requests per minute (over 10 RPM limit)
}

export function proClient() {
  const payload = JSON.stringify({
    message: 'Test query for pro',
    top_k: 2
  });

  const res = http.post(`${BASE_URL}/agent/query`, payload, {
    headers: {
      'Content-Type': 'application/json',
      'X-Client-ID': 'pro-mixed-001',
    },
  });

  console.log(`[PRO] Status: ${res.status}`);

  check(res, {
    'pro - is 200': (r) => r.status === 200,
  });
  if (res.status === 429) {
    console.log(`  ⚠ RATE LIMITED - Retry after ${res.headers['Retry-After']}s`);
  }
  sleep(0.5);  // 40 requests per minute (under 60 RPM limit)
}
