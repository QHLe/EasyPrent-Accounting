import { useCallback, useEffect, useState } from 'react';
import { apiClient } from '../../api/client';
import type { components } from '../../api/schema';

type Metering = components['schemas']['MeteringResponse'];
type MeterWrite = components['schemas']['MeterWrite'];
type ReadingWrite = components['schemas']['ReadingWrite'];

export function useMetering() {
  const [metering, setMetering] = useState<Metering | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const response = await apiClient.GET('/api/v1/metering');
      if (!response.data) throw new Error('Zählerdaten konnten nicht geladen werden.');
      setMetering(response.data);
    } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { void refresh(); }, [refresh]);

  const createMeter = async (body: MeterWrite) => {
    await apiClient.POST('/api/v1/meters', { body }); await refresh();
  };
  const updateMeter = async (meterId: number, body: MeterWrite) => {
    await apiClient.PUT('/api/v1/meters/{meter_id}', { params: { path: { meter_id: meterId } }, body }); await refresh();
  };
  const archiveMeter = async (meterId: number) => {
    await apiClient.POST('/api/v1/meters/{meter_id}/archive', { params: { path: { meter_id: meterId } } }); await refresh();
  };
  const restoreMeter = async (meterId: number) => {
    await apiClient.POST('/api/v1/meters/{meter_id}/restore', { params: { path: { meter_id: meterId } } }); await refresh();
  };
  const deleteMeter = async (meterId: number) => {
    await apiClient.DELETE('/api/v1/meters/{meter_id}', { params: { path: { meter_id: meterId } } }); await refresh();
  };
  const createReading = async (body: ReadingWrite) => {
    await apiClient.POST('/api/v1/meter-readings', { body }); await refresh();
  };
  const deleteReading = async (readingId: number) => {
    await apiClient.DELETE('/api/v1/meter-readings/{reading_id}', { params: { path: { reading_id: readingId } } }); await refresh();
  };
  const consumption = async (meterId: number, start: string, end: string) => {
    const response = await apiClient.GET('/api/v1/meters/{meter_id}/consumption', { params: { path: { meter_id: meterId }, query: { start, end } } });
    if (!response.data) throw new Error('Verbrauch konnte nicht geladen werden.');
    return response.data;
  };

  return { metering, loading, error, refresh, createMeter, updateMeter, archiveMeter, restoreMeter, deleteMeter, createReading, deleteReading, consumption };
}
