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
  vus: 1,  // 1 virtual user
  iterations: 20,  // 20 total requests
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

  console.log(`Request ${__ITER + 1}/20 - Status: ${res.status} - Remaining: ${res.headers['X-Ratelimit-Remaining'] || 'N/A'}`);

  check(res, {
    'is 200 or 429': (r) => r.status === 200 || r.status === 429,
  });

  if (res.status === 429) {
    console.log(`  ⚠ RATE LIMITED - Retry after ${res.headers['Retry-After']}s`);
  }

  sleep(3);  // 3 seconds between requests = 20 requests per minute
}


// simple_test_pro.js
/**
 * Simple test: Pro tier staying under limit
 * Sends 50 requests in 60 seconds (under 60 RPM limit)
 *
 * Save this as: simple_test_pro.js
 * Run with: k6 run simple_test_pro.js
 */
/*
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
*/


// simple_test_mixed.js
/**
 * Simple test: Multiple clients simultaneously
 * Tests that rate limits are per-client
 *
 * Save this as: simple_test_mixed.js
 * Run with: k6 run simple_test_mixed.js
 */
/*
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

  sleep(5);  // 12 requests per minute (over 10 RPM limit)
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

  sleep(1.5);  // 40 requests per minute (under 60 RPM limit)
}
*/