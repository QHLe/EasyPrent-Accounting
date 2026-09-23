import { useCallback, useEffect, useState } from 'react';
import { apiClient } from '../../api/client';
import type { components } from '../../api/schema';

type Period = components['schemas']['SettlementPeriodWrite'];
type Settlement = components['schemas']['SettlementResponse'];
type Overview = components['schemas']['SettlementRunOverviewResponse'];
type Assets = components['schemas']['AssetListResponse'];
type RunWrite = components['schemas']['SettlementRunWrite'];

export function useSettlements() {
  const [assets, setAssets] = useState<Assets | null>(null);
  const [settlement, setSettlement] = useState<Settlement | null>(null);
  const [overview, setOverview] = useState<Overview | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void apiClient.GET('/api/v1/assets').then(result => {
      if (result.data) setAssets(result.data);
    }).catch(cause => setError(cause instanceof Error ? cause.message : String(cause)));
  }, []);

  const clear = useCallback(() => { setSettlement(null); setOverview(null); setError(null); }, []);

  const calculate = async (period: Period) => {
    setLoading(true); setError(null); setOverview(null);
    try {
      const result = await apiClient.GET('/api/v1/settlements', { params: { query: period } });
      if (!result.data) throw new Error('Abrechnung konnte nicht berechnet werden.');
      setSettlement(result.data);
    } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)); }
    finally { setLoading(false); }
  };
  const refresh = async (period: Period) => {
    setLoading(true); setError(null); setOverview(null);
    try {
      const result = await apiClient.POST('/api/v1/settlements/refresh', { body: period });
      if (!result.data) throw new Error('Abrechnung konnte nicht aktualisiert werden.');
      setSettlement(result.data.settlement);
      return result.data.import;
    } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)); throw cause; }
    finally { setLoading(false); }
  };
  const loadRun = useCallback(async (id: string) => {
    const result = await apiClient.GET('/api/v1/settlement-runs/{settlement_id}', { params: { path: { settlement_id: id } } });
    if (!result.data) throw new Error('Abrechnungslauf konnte nicht geladen werden.');
    setOverview(result.data);
    setSettlement(result.data.settlement);
  }, []);
  const findRun = async (body: RunWrite) => {
    setLoading(true); setError(null);
    try {
      const result = await apiClient.GET('/api/v1/settlement-runs', { params: { query: body } });
      if (result.data?.id) await loadRun(result.data.id);
      else setOverview(null);
      return Boolean(result.data?.id);
    } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)); throw cause; }
    finally { setLoading(false); }
  };
  const createRun = async (body: RunWrite) => {
    setLoading(true); setError(null);
    try {
      const result = await apiClient.POST('/api/v1/settlement-runs', { body });
      if (!result.data) throw new Error('Abrechnungslauf konnte nicht erstellt werden.');
      await loadRun(result.data.id);
    } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)); throw cause; }
    finally { setLoading(false); }
  };
  const refreshPayments = async (id: string) => {
    const result = await apiClient.POST('/api/v1/settlement-runs/{settlement_id}/payments/refresh', { params: { path: { settlement_id: id } } });
    if (!result.data) throw new Error('Zahlungen konnten nicht aktualisiert werden.');
    setOverview(result.data.overview);
    setSettlement(result.data.overview.settlement);
  };
  const considerAll = async (id: string) => {
    const result = await apiClient.POST('/api/v1/settlement-runs/{settlement_id}/payments/consider-all', { params: { path: { settlement_id: id } } });
    if (!result.data) throw new Error('Zahlungen konnten nicht zugeordnet werden.');
    setOverview(result.data); setSettlement(result.data.settlement);
  };
  const consider = async (id: string, splitGuid: string) => {
    const result = await apiClient.POST('/api/v1/settlement-runs/{settlement_id}/payments/{split_guid}/consider', { params: { path: { settlement_id: id, split_guid: splitGuid } } });
    if (!result.data) throw new Error('Zahlung konnte nicht zugeordnet werden.');
    setOverview(result.data); setSettlement(result.data.settlement);
  };
  const unassign = async (id: string, splitGuid: string) => {
    const result = await apiClient.POST('/api/v1/settlement-runs/{settlement_id}/payments/{split_guid}/unassign', { params: { path: { settlement_id: id, split_guid: splitGuid } } });
    if (!result.data) throw new Error('Zahlungszuordnung konnte nicht entfernt werden.');
    setOverview(result.data); setSettlement(result.data.settlement);
  };

  return { assets, settlement, overview, loading, error, clear, calculate, refresh, findRun, createRun, refreshPayments, considerAll, consider, unassign };
}
