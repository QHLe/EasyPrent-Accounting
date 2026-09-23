import { useCallback, useEffect, useState } from 'react';
import { apiClient } from '../../api/client';
import type { components } from '../../api/schema';

type ExpenseList = components['schemas']['ExpenseListResponse'];
type ExpenseWrite = components['schemas']['ExpenseWrite'];
type AssetList = components['schemas']['AssetListResponse'];
type Metering = components['schemas']['MeteringResponse'];

export function useExpenses() {
  const [expenses, setExpenses] = useState<ExpenseList | null>(null);
  const [assets, setAssets] = useState<AssetList | null>(null);
  const [metering, setMetering] = useState<Metering | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [expenseResult, assetResult, meterResult] = await Promise.all([
        apiClient.GET('/api/v1/expenses'),
        apiClient.GET('/api/v1/assets'),
        apiClient.GET('/api/v1/metering'),
      ]);
      if (!expenseResult.data || !assetResult.data || !meterResult.data) {
        throw new Error('Die Kostendaten konnten nicht geladen werden.');
      }
      setExpenses(expenseResult.data);
      setAssets(assetResult.data);
      setMetering(meterResult.data);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  const create = async (body: ExpenseWrite) => {
    await apiClient.POST('/api/v1/expenses', { body });
    await refresh();
  };
  const update = async (id: number, body: ExpenseWrite) => {
    await apiClient.PUT('/api/v1/expenses/{expense_id}', { params: { path: { expense_id: id } }, body });
    await refresh();
  };
  const archive = async (id: number) => {
    await apiClient.POST('/api/v1/expenses/{expense_id}/archive', { params: { path: { expense_id: id } } });
    await refresh();
  };
  const restore = async (id: number) => {
    await apiClient.POST('/api/v1/expenses/{expense_id}/restore', { params: { path: { expense_id: id } } });
    await refresh();
  };
  const remove = async (id: number) => {
    await apiClient.DELETE('/api/v1/expenses/{expense_id}', { params: { path: { expense_id: id } } });
    await refresh();
  };

  return { expenses, assets, metering, loading, error, refresh, create, update, archive, restore, remove };
}
