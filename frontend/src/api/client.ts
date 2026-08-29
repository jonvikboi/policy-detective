import { Scan, ScanReport, Experiment, Policy, PolicyClaim, Verdict } from '../types';

const API_BASE = '/api';

export async function checkBackendHealth(): Promise<{ status: string; version: string; webcmd_binary: string }> {
  const res = await fetch('/health');
  if (!res.ok) throw new Error('Backend is unreachable');
  return res.json();
}

export async function createScan(url: string): Promise<Scan> {
  const res = await fetch(`${API_BASE}/scans`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to create scan' }));
    throw new Error(err.detail || 'Failed to create scan');
  }

  return res.json();
}

export async function getScan(id: string): Promise<Scan> {
  const res = await fetch(`${API_BASE}/scans/${id}`);
  if (!res.ok) throw new Error('Failed to fetch scan');
  return res.json();
}

export async function getScanStatus(id: string): Promise<{
  id: string;
  status: string;
  progress: number;
  current_stage: string;
  stage_details: string;
  error?: string | null;
  recent_events: Array<{ type: string; data: any; created_at: string }>;
}> {
  const res = await fetch(`${API_BASE}/scans/${id}/status`);
  if (!res.ok) throw new Error('Failed to fetch scan status');
  return res.json();
}

export async function getScanReport(id: string): Promise<ScanReport> {
  const res = await fetch(`${API_BASE}/scans/${id}/report`);
  if (!res.ok) throw new Error('Failed to fetch scan report');
  return res.json();
}

export async function getScanEvidence(id: string): Promise<Experiment[]> {
  const res = await fetch(`${API_BASE}/scans/${id}/evidence`);
  if (!res.ok) throw new Error('Failed to fetch evidence');
  return res.json();
}

export async function getScanPolicies(id: string): Promise<Policy[]> {
  const res = await fetch(`${API_BASE}/scans/${id}/policies`);
  if (!res.ok) throw new Error('Failed to fetch policies');
  return res.json();
}

export async function getScanClaims(id: string): Promise<PolicyClaim[]> {
  const res = await fetch(`${API_BASE}/scans/${id}/claims`);
  if (!res.ok) throw new Error('Failed to fetch claims');
  return res.json();
}

export async function getScanVerdicts(id: string): Promise<Verdict[]> {
  const res = await fetch(`${API_BASE}/scans/${id}/verdicts`);
  if (!res.ok) throw new Error('Failed to fetch verdicts');
  return res.json();
}

/**
 * Subscribes to real-time events via Server-Sent Events with polling fallback.
 */
export function subscribeToScanEvents(
  scanId: string,
  onEvent: (type: string, data: any) => void,
  onError: (err: any) => void
): () => void {
  let eventSource: EventSource | null = null;
  let pollInterval: any = null;
  let isClosed = false;

  try {
    eventSource = new EventSource(`${API_BASE}/scans/${scanId}/events`);

    eventSource.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        onEvent('message', data);
      } catch (err) {
        onEvent('message', e.data);
      }
    };

    const eventTypes = [
      'stage_change',
      'policy_found',
      'links_extracted',
      'policy_links_identified',
      'claims_extracted',
      'consent_interaction',
      'experiment_completed',
      'verdict_generated',
      'workflow_reuse',
      'progress',
      'error',
      'done'
    ];

    eventTypes.forEach((type) => {
      eventSource?.addEventListener(type, (e: any) => {
        try {
          const data = JSON.parse(e.data);
          onEvent(type, data);
          if (type === 'done') {
            cleanup();
          }
        } catch (err) {
          onEvent(type, e.data);
        }
      });
    });

    eventSource.onerror = (err) => {
      // Fallback to polling if SSE fails
      console.warn('SSE connection interrupted, falling back to status polling');
      if (eventSource) {
        eventSource.close();
        eventSource = null;
      }
      startPolling();
    };
  } catch (err) {
    startPolling();
  }

  function startPolling() {
    if (isClosed || pollInterval) return;
    pollInterval = setInterval(async () => {
      try {
        const status = await getScanStatus(scanId);
        onEvent('progress', {
          status: status.status,
          progress: status.progress,
          stage: status.current_stage,
          stage_details: status.stage_details,
        });

        if (status.recent_events && status.recent_events.length > 0) {
          status.recent_events.forEach((ev) => {
            onEvent(ev.type, ev.data);
          });
        }

        if (status.status === 'completed' || status.status === 'failed') {
          onEvent('done', { status: status.status });
          cleanup();
        }
      } catch (e) {
        onError(e);
      }
    }, 2000);
  }

  function cleanup() {
    isClosed = true;
    if (eventSource) {
      eventSource.close();
      eventSource = null;
    }
    if (pollInterval) {
      clearInterval(pollInterval);
      pollInterval = null;
    }
  }

  return cleanup;
}
