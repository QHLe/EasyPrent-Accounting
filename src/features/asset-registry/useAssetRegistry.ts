import { useState, useCallback, useEffect } from 'react';
import { apiClient } from '../../api/client';
import type { components } from '../../api/schema';

type AssetListResponse = components['schemas']['AssetListResponse'];
type PropertyWrite = components['schemas']['PropertyWrite'];
type BuildingWrite = components['schemas']['BuildingWrite'];
type UnitWrite = components['schemas']['UnitWrite'];
type RoomWrite = components['schemas']['RoomWrite'];

export function useAssetRegistry() {
  const [assets, setAssets] = useState<AssetListResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchAssets = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await apiClient.GET('/api/v1/assets');
      if (res.data) setAssets(res.data);
    } catch (err: any) {
      setError(err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAssets();
  }, [fetchAssets]);

  const mutate = async (method: 'POST' | 'PUT' | 'DELETE', url: any, params?: any, body?: any) => {
    await (apiClient as any)[method](url, { params, body });
    await fetchAssets();
  };

  const createProperty = (data: PropertyWrite) => mutate('POST', '/api/v1/properties', undefined, data);
  const updateProperty = (id: number, data: PropertyWrite) => mutate('PUT', '/api/v1/properties/{property_id}', { path: { property_id: id } }, data);
  const archiveProperty = (id: number) => mutate('POST', '/api/v1/properties/{property_id}/archive', { path: { property_id: id } });
  const deleteProperty = (id: number) => mutate('DELETE', '/api/v1/properties/{property_id}', { path: { property_id: id } });

  const createBuilding = (data: BuildingWrite) => mutate('POST', '/api/v1/buildings', undefined, data);
  const updateBuilding = (id: number, data: BuildingWrite) => mutate('PUT', '/api/v1/buildings/{building_id}', { path: { building_id: id } }, data);
  const archiveBuilding = (id: number) => mutate('POST', '/api/v1/buildings/{building_id}/archive', { path: { building_id: id } });
  const deleteBuilding = (id: number) => mutate('DELETE', '/api/v1/buildings/{building_id}', { path: { building_id: id } });

  const createUnit = (data: UnitWrite) => mutate('POST', '/api/v1/units', undefined, data);
  const updateUnit = (id: number, data: UnitWrite) => mutate('PUT', '/api/v1/units/{unit_id}', { path: { unit_id: id } }, data);
  const archiveUnit = (id: number) => mutate('POST', '/api/v1/units/{unit_id}/archive', { path: { unit_id: id } });
  const deleteUnit = (id: number) => mutate('DELETE', '/api/v1/units/{unit_id}', { path: { unit_id: id } });

  const createRoom = (data: RoomWrite) => mutate('POST', '/api/v1/rooms', undefined, data);
  const updateRoom = (id: number, data: RoomWrite) => mutate('PUT', '/api/v1/rooms/{room_id}', { path: { room_id: id } }, data);
  const archiveRoom = (id: number) => mutate('POST', '/api/v1/rooms/{room_id}/archive', { path: { room_id: id } });
  const deleteRoom = (id: number) => mutate('DELETE', '/api/v1/rooms/{room_id}', { path: { room_id: id } });

  const restoreAsset = async (type: 'property' | 'building' | 'unit' | 'room', id: number) => {
    const endpoints = {
      property: `/api/v1/properties/${id}/restore`,
      building: `/api/v1/buildings/${id}/restore`,
      unit: `/api/v1/units/${id}/restore`,
      room: `/api/v1/rooms/${id}/restore`
    } as const;
    await apiClient.POST(endpoints[type] as any, { params: { path: { [`${type}_id`]: id } as any } } as any);
    await fetchAssets();
  };

  return {
    assets,
    isLoading,
    error,
    refresh: fetchAssets,
    createProperty, updateProperty, archiveProperty, deleteProperty,
    createBuilding, updateBuilding, archiveBuilding, deleteBuilding,
    createUnit, updateUnit, archiveUnit, deleteUnit,
    createRoom, updateRoom, archiveRoom, deleteRoom,
    restoreAsset
  };
}
