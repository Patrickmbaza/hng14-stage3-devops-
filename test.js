import http from 'k6/http';
import { sleep, check } from 'k6';

export const options = {
  stages: [
    { duration: '2m', target: 10 }, // warm up
    { duration: '3m', target: 50 }, // light load
    { duration: '3m', target: 100 }, // moderate load
    { duration: '3m', target: 200 }, // heavy load
    { duration: '2m', target: 0 }, // cool down
  ],
  thresholds: {
    http_req_failed: ['rate<0.05'], // fail if >5% errors
    http_req_duration: ['p(95)<3000'], // fail if p95 > 3s
  },
};

export default function () {
  let res = http.get('http://mbaza.duckdns.org:8081');
  check(res, { 'status 200': (r) => r.status === 200 });
  sleep(1 + Math.random() * 2); // randomize think time
}