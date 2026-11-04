import http from 'k6/http';
import { check, sleep, group } from 'k6';
import { Rate, Trend } from 'k6/metrics';

// Custom metrics for tracking key stages
const failureRate = new Rate('failed_requests');
const noteCreateLatency = new Trend('note_create_duration');
const noteUpdateLatency = new Trend('note_update_duration');

// Target endpoint: defaults to local server, overridable via BASE_URL environment variable
const BASE_URL = __ENV.BASE_URL || 'http://127.0.0.1:8000';

// Guide workload stages:
// - 1 minute ramp up to 10 users
// - 2 minutes ramp up to 40 users
// - 5 minutes steady state at 40 users
// - 1 minute ramp down to 0 users
const defaultStages = [
  { duration: '1m', target: 10 },
  { duration: '2m', target: 40 },
  { duration: '5m', target: 40 },
  { duration: '1m', target: 0 },
];

// Quick smoke test stages for local verification when QUICK=true
const quickStages = [
  { duration: '10s', target: 2 },
  { duration: '20s', target: 5 },
  { duration: '10s', target: 0 },
];

export const options = {
  stages: __ENV.QUICK === 'true' ? quickStages : defaultStages,
  thresholds: {
    // Exact guide thresholds:
    // 1. Less than 1% failed requests
    http_req_failed: ['rate<0.01'],
    // 2. p95 latency below 800 ms
    http_req_duration: ['p(95)<800'],
  },
};

export default function () {
  const commonHeaders = {
    'Accept': 'application/json',
    'X-Requested-With': 'cloudnotes',
  };

  const jsonHeaders = {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
    'X-Requested-With': 'cloudnotes',
  };

  // 1. Login (Demo account authentication)
  group('01_Login', () => {
    const loginRes = http.post(
      `${BASE_URL}/api/auth/demo`,
      JSON.stringify({}),
      { headers: jsonHeaders }
    );
    const passed = check(loginRes, {
      'login status is 200': (r) => r.status === 200,
      'user id returned': (r) => {
        try {
          const body = JSON.parse(r.body);
          return body && body.id !== undefined;
        } catch {
          return false;
        }
      },
    });
    failureRate.add(!passed);
  });

  // 2. List notes
  let sampleNoteId = null;
  group('02_ListNotes', () => {
    const listRes = http.get(
      `${BASE_URL}/api/notes?view=all&sort=updated`,
      { headers: commonHeaders }
    );
    const passed = check(listRes, {
      'list notes status is 200': (r) => r.status === 200,
      'notes returned as array': (r) => {
        try {
          const body = JSON.parse(r.body);
          const notes = Array.isArray(body) ? body : (body.notes || []);
          if (notes.length > 0) {
            sampleNoteId = notes[0].id;
          }
          return true;
        } catch {
          return false;
        }
      },
    });
    failureRate.add(!passed);
  });

  // 3. Open note
  group('03_OpenNote', () => {
    if (sampleNoteId) {
      const openRes = http.get(
        `${BASE_URL}/api/notes/${sampleNoteId}`,
        { headers: commonHeaders }
      );
      const passed = check(openRes, {
        'open note status is 200': (r) => r.status === 200,
        'note title present': (r) => {
          try {
            const body = JSON.parse(r.body);
            return body && body.title !== undefined;
          } catch {
            return false;
          }
        },
      });
      failureRate.add(!passed);
    }
  });

  // 4. Create note
  let createdNoteId = null;
  group('04_CreateNote', () => {
    const newNotePayload = JSON.stringify({
      title: `Load Test Note VU ${__VU} Iter ${__ITER}`,
      content: `# Performance Test\nCreated by virtual user ${__VU} in iteration ${__ITER} at ${new Date().toISOString()}.\n\nTesting concurrent write throughput.`,
      tags: ['loadtest', 'k6', 'autoscale'],
    });

    const createStart = Date.now();
    const createRes = http.post(
      `${BASE_URL}/api/notes`,
      newNotePayload,
      { headers: jsonHeaders }
    );
    noteCreateLatency.add(Date.now() - createStart);

    const passed = check(createRes, {
      'create note status is 201': (r) => r.status === 201,
      'created note id present': (r) => {
        try {
          const body = JSON.parse(r.body);
          if (body && body.id) {
            createdNoteId = body.id;
            return true;
          }
          return false;
        } catch {
          return false;
        }
      },
    });
    failureRate.add(!passed);
  });

  // 5. Update note
  group('05_UpdateNote', () => {
    if (createdNoteId) {
      const updatePayload = JSON.stringify({
        title: `Updated Note VU ${__VU} Iter ${__ITER}`,
        content: `# Updated Performance Test\nModified by virtual user ${__VU} at ${new Date().toISOString()}.\n\nAutosave and markdown update check.`,
      });

      const updateStart = Date.now();
      const updateRes = http.patch(
        `${BASE_URL}/api/notes/${createdNoteId}`,
        updatePayload,
        { headers: jsonHeaders }
      );
      noteUpdateLatency.add(Date.now() - updateStart);

      const passed = check(updateRes, {
        'update note status is 200': (r) => r.status === 200,
        'updated version incremented': (r) => {
          try {
            const body = JSON.parse(r.body);
            return body && body.version >= 2;
          } catch {
            return false;
          }
        },
      });
      failureRate.add(!passed);
    }
  });

  // 6. Search notes
  group('06_Search', () => {
    const query = (__ITER % 2 === 0) ? 'model' : 'test';
    const searchRes = http.get(
      `${BASE_URL}/api/notes?q=${query}`,
      { headers: commonHeaders }
    );
    const passed = check(searchRes, {
      'search status is 200': (r) => r.status === 200,
    });
    failureRate.add(!passed);
  });

  // 7. System Status (/api/status)
  group('07_SystemStatus', () => {
    const statusRes = http.get(
      `${BASE_URL}/api/status`,
      { headers: commonHeaders }
    );
    const passed = check(statusRes, {
      'status endpoint is 200': (r) => r.status === 200,
      'db and storage ok': (r) => {
        try {
          const body = JSON.parse(r.body);
          return body.db_ok === true && body.storage_ok === true;
        } catch {
          return false;
        }
      },
    });
    failureRate.add(!passed);
  });

  // 8. Public Health (/api/health)
  group('08_PublicHealth', () => {
    const healthRes = http.get(
      `${BASE_URL}/api/health`,
      { headers: commonHeaders }
    );
    const passed = check(healthRes, {
      'health endpoint is 200': (r) => r.status === 200,
    });
    failureRate.add(!passed);
  });

  // Think time between iterations: 0.2s for quick local runs, 1s for full benchmark
  sleep(__ENV.QUICK === 'true' ? 0.2 : 1);
}
