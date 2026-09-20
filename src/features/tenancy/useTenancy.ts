import { useState, useCallback, useEffect } from 'react';
import { apiClient } from '../../api/client';
import type { components } from '../../api/schema';

type TenancyResponse = components['schemas']['TenancyResponse'];
type TenantWrite = components['schemas']['TenantWrite'];
type LeaseWrite = components['schemas']['LeaseWrite'];

export function useTenancy() {
  const [tenancy, setTenancy] = useState<TenancyResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchTenancy = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await apiClient.GET('/api/v1/tenancy');
      if (res.data) setTenancy(res.data);
    } catch (err: any) {
      setError(err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchTenancy();
  }, [fetchTenancy]);

  const createTenant = async (data: TenantWrite) => {
    await apiClient.POST('/api/v1/tenants', { body: data });
    await fetchTenancy();
  };

  const updateTenant = async (id: number, data: TenantWrite) => {
    await apiClient.PUT('/api/v1/tenants/{tenant_id}', { params: { path: { tenant_id: id } }, body: data });
    await fetchTenancy();
  };

  const deleteTenant = async (id: number) => {
    await apiClient.DELETE('/api/v1/tenants/{tenant_id}', { params: { path: { tenant_id: id } } });
    await fetchTenancy();
  };

  const createLease = async (data: LeaseWrite) => {
    await apiClient.POST('/api/v1/leases', { body: data });
    await fetchTenancy();
  };

  const updateLease = async (id: number, data: LeaseWrite) => {
    await apiClient.PUT('/api/v1/leases/{lease_id}', { params: { path: { lease_id: id } }, body: data });
    await fetchTenancy();
  };

  const deleteLease = async (id: number) => {
    await apiClient.DELETE('/api/v1/leases/{lease_id}', { params: { path: { lease_id: id } } });
    await fetchTenancy();
  };

  return {
    tenancy,
    isLoading,
    error,
    refresh: fetchTenancy,
    createTenant, updateTenant, deleteTenant,
    createLease, updateLease, deleteLease
  };
}
