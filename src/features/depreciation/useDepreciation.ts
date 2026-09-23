import { useCallback, useEffect, useState } from 'react';
import { apiClient } from '../../api/client';
import type { components } from '../../api/schema';

type Asset = components['schemas']['AssetResponse'];
type AssetWrite = components['schemas']['AssetWrite'];
type Schedule = components['schemas']['ScheduleResponse'];
type Property = components['schemas']['PropertyResponse'];

export function useDepreciation(year: number) {
  const [assets, setAssets] = useState<Asset[]>([]);
  const [properties, setProperties] = useState<Property[]>([]);
  const [schedule, setSchedule] = useState<Schedule | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const refresh = useCallback(async () => {
    setLoading(true); setError(null); setSchedule(null);
    try {
      const [assetResult, propertyResult, scheduleResult] = await Promise.all([
        apiClient.GET('/api/v1/depreciation/assets'),
        apiClient.GET('/api/v1/assets'),
        apiClient.GET('/api/v1/depreciation/schedule/{year}', { params: { path: { year } } }),
      ]);
      if (!assetResult.data || !propertyResult.data || !scheduleResult.data) throw new Error('Abschreibungen konnten nicht geladen werden.');
      setAssets(assetResult.data);
      setProperties(propertyResult.data.properties);
      setSchedule(scheduleResult.data);
    } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)); }
    finally { setLoading(false); }
  }, [year]);
  useEffect(() => { void refresh(); }, [refresh]);
  const create = async (body: AssetWrite) => {
    await apiClient.POST('/api/v1/depreciation/assets', { body });
    await refresh();
  };
  return { assets, properties, schedule, loading, error, refresh, create };
}
