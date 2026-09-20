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

  const createProperty = async (data: PropertyWrite) => {
    await apiClient.POST('/api/v1/properties', { body: data });
    await fetchAssets();
  };

  const updateProperty = async (id: number, data: PropertyWrite) => {
    await apiClient.PUT('/api/v1/properties/{property_id}', {
      params: { path: { property_id: id } },
      body: data
    });
    await fetchAssets();
  };

  const archiveProperty = async (id: number) => {
    await apiClient.POST('/api/v1/properties/{property_id}/archive', { params: { path: { property_id: id } } });
    await fetchAssets();
  };
  
  const deleteProperty = async (id: number) => {
    await apiClient.DELETE('/api/v1/properties/{property_id}', { params: { path: { property_id: id } } });
    await fetchAssets();
  };

  const createBuilding = async (data: BuildingWrite) => {
    await apiClient.POST('/api/v1/buildings', { body: data });
    await fetchAssets();
  };

  const updateBuilding = async (id: number, data: BuildingWrite) => {
    await apiClient.PUT('/api/v1/buildings/{building_id}', {
      params: { path: { building_id: id } },
      body: data
    });
    await fetchAssets();
  };

  const archiveBuilding = async (id: number) => {
    await apiClient.POST('/api/v1/buildings/{building_id}/archive', { params: { path: { building_id: id } } });
    await fetchAssets();
  };

  const deleteBuilding = async (id: number) => {
    await apiClient.DELETE('/api/v1/buildings/{building_id}', { params: { path: { building_id: id } } });
    await fetchAssets();
  };

  const createUnit = async (data: UnitWrite) => {
    await apiClient.POST('/api/v1/units', { body: data });
    await fetchAssets();
  };

  const updateUnit = async (id: number, data: UnitWrite) => {
    await apiClient.PUT('/api/v1/units/{unit_id}', {
      params: { path: { unit_id: id } },
      body: data
    });
    await fetchAssets();
  };

  const archiveUnit = async (id: number) => {
    await apiClient.POST('/api/v1/units/{unit_id}/archive', { params: { path: { unit_id: id } } });
    await fetchAssets();
  };

  const deleteUnit = async (id: number) => {
    await apiClient.DELETE('/api/v1/units/{unit_id}', { params: { path: { unit_id: id } } });
    await fetchAssets();
  };

  const createRoom = async (data: RoomWrite) => {
    await apiClient.POST('/api/v1/rooms', { body: data });
    await fetchAssets();
  };

  const updateRoom = async (id: number, data: RoomWrite) => {
    await apiClient.PUT('/api/v1/rooms/{room_id}', {
      params: { path: { room_id: id } },
      body: data
    });
    await fetchAssets();
  };

  const archiveRoom = async (id: number) => {
    await apiClient.POST('/api/v1/rooms/{room_id}/archive', { params: { path: { room_id: id } } });
    await fetchAssets();
  };

  const deleteRoom = async (id: number) => {
    await apiClient.DELETE('/api/v1/rooms/{room_id}', { params: { path: { room_id: id } } });
    await fetchAssets();
  };

  const restoreAsset = async (type: 'property' | 'building' | 'unit' | 'room', id: number) => {
    switch (type) {
      case 'property':
        await apiClient.POST('/api/v1/properties/{property_id}/restore', { params: { path: { property_id: id } } });
        break;
      case 'building':
        await apiClient.POST('/api/v1/buildings/{building_id}/restore', { params: { path: { building_id: id } } });
        break;
      case 'unit':
        await apiClient.POST('/api/v1/units/{unit_id}/restore', { params: { path: { unit_id: id } } });
        break;
      case 'room':
        await apiClient.POST('/api/v1/rooms/{room_id}/restore', { params: { path: { room_id: id } } });
        break;
    }
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
