import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  vus: 2,  // 2 virtual users
  iterations: 50,  // 50 total requests
  duration: '60s',
};

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';

export default function () {
  const payload = JSON.stringify({
    message: 'What are the monitoring thresholds?',
    top_k: 3
  });

  const params = {
    headers: {
      'Content-Type': 'application/json',
      'X-Client-ID': 'pro-simple-test',
    },
  };

  const res = http.post(`${BASE_URL}/agent/query`, payload, params);

  console.log(`[PRO] Request ${__ITER + 1}/50 - Status: ${res.status} - Remaining: ${res.headers['X-Ratelimit-Remaining'] || 'N/A'}`);

  check(res, {
    'is 200': (r) => r.status === 200,
  });

  if (res.status === 429) {
    console.log(`  ⚠ UNEXPECTED RATE LIMIT!`);
  }

  sleep(1.2);  // 1.2 seconds between requests = ~50 requests per minute
}

