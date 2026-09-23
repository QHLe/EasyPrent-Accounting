import { useCallback, useEffect, useState } from 'react';
import { apiClient } from '../../api/client';
import type { components } from '../../api/schema';

type Summary = components['schemas']['DashboardSummaryResponse'];

export function useDashboard() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const refresh = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const result = await apiClient.GET('/api/v1/dashboard/summary');
      if (!result.data) throw new Error('Übersicht konnte nicht geladen werden.');
      setSummary(result.data);
    } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { void refresh(); }, [refresh]);
  return { summary, loading, error, refresh };
}
