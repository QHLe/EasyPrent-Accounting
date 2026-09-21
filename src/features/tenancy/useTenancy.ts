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

  const mutate = async (method: 'POST' | 'PUT' | 'DELETE', url: any, params?: any, body?: any) => {
    await (apiClient as any)[method](url, { params, body });
    await fetchTenancy();
  };

  const createTenant = (data: TenantWrite) => mutate('POST', '/api/v1/tenants', undefined, data);
  const updateTenant = (id: number, data: TenantWrite) => mutate('PUT', '/api/v1/tenants/{tenant_id}', { path: { tenant_id: id } }, data);
  const deleteTenant = (id: number) => mutate('DELETE', '/api/v1/tenants/{tenant_id}', { path: { tenant_id: id } });

  const createLease = (data: LeaseWrite) => mutate('POST', '/api/v1/leases', undefined, data);
  const updateLease = (id: number, data: LeaseWrite) => mutate('PUT', '/api/v1/leases/{lease_id}', { path: { lease_id: id } }, data);
  const deleteLease = (id: number) => mutate('DELETE', '/api/v1/leases/{lease_id}', { path: { lease_id: id } });

  return {
    tenancy,
    isLoading,
    error,
    refresh: fetchTenancy,
    createTenant, updateTenant, deleteTenant,
    createLease, updateLease, deleteLease
  };
}
