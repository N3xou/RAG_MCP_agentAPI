// load_test.js
/**
 * k6 Load Test for DevOps Agent Rate Limiter
 *
 * Tests three scenarios:
 * 1. Basic tier - Exceeds limit (should get 429s)
 * 2. Pro tier - Stays under limit (should get 200s)
 * 3. VIP tier - High volume (should get 200s)
 *
 * Run with: k6 run load_test.js
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Counter, Rate, Trend } from 'k6/metrics';

// Custom metrics
const rateLimitedRequests = new Counter('rate_limited_requests');
const successfulRequests = new Counter('successful_requests');
const rateLimitRate = new Rate('rate_limit_rate');
const responseTimesByTier = new Trend('response_times_by_tier');

// Configuration
const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';

// Test scenarios
export const options = {
  scenarios: {
    // Scenario 1: Basic tier - 20 requests in 1 minute (2x the 10 RPM limit)
    basic_tier_overload: {
      executor: 'constant-arrival-rate',
      rate: 20,  // 20 requests
      timeUnit: '1m',  // per minute
      duration: '1m',
      preAllocatedVUs: 5,
      maxVUs: 10,
      exec: 'basicTierTest',
      tags: { scenario: 'basic_overload' },
    },

    // Scenario 2: Pro tier - 50 requests in 1 minute (under 60 RPM limit)
    pro_tier_normal: {
      executor: 'constant-arrival-rate',
      rate: 50,  // 50 requests
      timeUnit: '1m',  // per minute
      duration: '1m',
      preAllocatedVUs: 10,
      maxVUs: 20,
      exec: 'proTierTest',
      tags: { scenario: 'pro_normal' },
      startTime: '0s',  // Run concurrently
    },

    // Scenario 3: VIP tier - 250 requests in 1 minute (under 300 RPM limit)
    vip_tier_high_volume: {
      executor: 'constant-arrival-rate',
      rate: 250,  // 250 requests
      timeUnit: '1m',  // per minute
      duration: '1m',
      preAllocatedVUs: 20,
      maxVUs: 40,
      exec: 'vipTierTest',
      tags: { scenario: 'vip_high_volume' },
      startTime: '0s',  // Run concurrently
    },
  },

  thresholds: {
    // Basic tier should have high rate limit rate
    'rate_limit_rate{scenario:basic_overload}': ['rate>0.4'],  // >40% should be rate limited

    // Pro and VIP should have low rate limit rate
    'rate_limit_rate{scenario:pro_normal}': ['rate<0.2'],  // <20% rate limited
    'rate_limit_rate{scenario:vip_high_volume}': ['rate<0.2'],  // <20% rate limited

    // Response times should be reasonable
    'http_req_duration': ['p(95)<500'],
  },
};

// Test function for Basic tier
export function basicTierTest() {
  const payload = JSON.stringify({
    message: 'What is the deployment procedure?',
    top_k: 3
  });

  const params = {
    headers: {
      'Content-Type': 'application/json',
      'X-Client-ID': 'basic-test-001',
    },
    tags: { tier: 'basic' },
  };

  const res = http.post(`${BASE_URL}/agent/query`, payload, params);

  // Check response
  const isSuccess = check(res, {
    'status is 200 or 429': (r) => r.status === 200 || r.status === 429,
  });

  if (res.status === 429) {
    rateLimitedRequests.add(1);
    rateLimitRate.add(1);

    // Verify rate limit headers
    check(res, {
      'has X-RateLimit-Limit header': (r) => r.headers['X-Ratelimit-Limit'] !== undefined,
      'has Retry-After header': (r) => r.headers['Retry-After'] !== undefined,
    });

    console.log(`[BASIC] Rate limited - Retry-After: ${res.headers['Retry-After']}s`);
  } else if (res.status === 200) {
    successfulRequests.add(1);
    rateLimitRate.add(0);
    console.log(`[BASIC] Success - Remaining: ${res.headers['X-Ratelimit-Remaining']}`);
  }

  responseTimesByTier.add(res.timings.duration, { tier: 'basic' });
}

// Test function for Pro tier
export function proTierTest() {
  const payload = JSON.stringify({
    message: 'What are the incident severity levels?',
    top_k: 3
  });

  const params = {
    headers: {
      'Content-Type': 'application/json',
      'X-Client-ID': 'pro-test-001',
    },
    tags: { tier: 'pro' },
  };

  const res = http.post(`${BASE_URL}/agent/query`, payload, params);

  check(res, {
    'status is 200': (r) => r.status === 200,
  });

  if (res.status === 429) {
    rateLimitedRequests.add(1);
    rateLimitRate.add(1);
    console.log(`[PRO] Unexpected rate limit!`);
  } else if (res.status === 200) {
    successfulRequests.add(1);
    rateLimitRate.add(0);
  }

  responseTimesByTier.add(res.timings.duration, { tier: 'pro' });
}

// Test function for VIP tier
export function vipTierTest() {
  const payload = JSON.stringify({
    message: 'Show me monitoring best practices',
    top_k: 3
  });

  const params = {
    headers: {
      'Content-Type': 'application/json',
      'X-Client-ID': 'vip-test-001',
    },
    tags: { tier: 'vip' },
  };

  const res = http.post(`${BASE_URL}/agent/query`, payload, params);

  check(res, {
    'status is 200': (r) => r.status === 200,
  });

  if (res.status === 429) {
    rateLimitedRequests.add(1);
    rateLimitRate.add(1);
    console.log(`[VIP] Unexpected rate limit!`);
  } else if (res.status === 200) {
    successfulRequests.add(1);
    rateLimitRate.add(0);
  }

  responseTimesByTier.add(res.timings.duration, { tier: 'vip' });
}

// Summary at the end
export function handleSummary(data) {
  console.log('\n=== RATE LIMITER TEST SUMMARY ===\n');

  const scenarios = data.root_group.groups;

  for (const [name, scenario] of Object.entries(scenarios)) {
    if (scenario.checks) {
      console.log(`\nScenario: ${name}`);
      console.log(`  Total requests: ${scenario.checks['status is 200 or 429']?.passes + scenario.checks['status is 200 or 429']?.fails || 0}`);
      console.log(`  Successful (200): ${scenario.checks['status is 200']?.passes || 0}`);
      console.log(`  Rate Limited (429): ${scenario.checks['status is 200 or 429']?.passes - scenario.checks['status is 200']?.passes || 0}`);
    }
  }

  return {
    'stdout': JSON.stringify(data, null, 2),
  };
}