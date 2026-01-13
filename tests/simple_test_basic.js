// simple_test_basic.js
/**
 * Simple test: Basic tier exceeding limit
 * Sends 20 requests in 60 seconds (2x the 10 RPM limit)
 *
 * Run with: k6 run simple_test_basic.js
 */

import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  vus: 2,  // 1 virtual user
  iterations: 25,  // 20 total requests
  duration: '60s',
};

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';

export default function () {
  const payload = JSON.stringify({
    message: 'What is the deployment procedure?',
    top_k: 3
  });

  const params = {
    headers: {
      'Content-Type': 'application/json',
      'X-Client-ID': 'basic-simple-test',
    },
  };

  const res = http.post(`${BASE_URL}/agent/query`, payload, params);

  console.log(`Request ${__ITER + 1}/25 - Status: ${res.status} - Remaining: ${res.headers['X-Ratelimit-Remaining'] || 'N/A'}`);

  check(res, {
    'is 200 or 429': (r) => r.status === 200 || r.status === 429,
  });

  if (res.status === 429) {
    console.log(`  ⚠ RATE LIMITED - Retry after ${res.headers['Retry-After']}s`);
  }

  sleep(3);  // 3 seconds between requests = 20 requests per minute
}




