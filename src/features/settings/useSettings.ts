import { useState, useCallback, useEffect } from 'react';
import { apiClient } from '../../api/client';
import type { components } from '../../api/schema';

type ApplicationSettingsResponse = components['schemas']['ApplicationSettingsResponse'];
type ApplicationSettingsWrite = components['schemas']['ApplicationSettingsWrite'];
type PaperlessSettingsResponse = components['schemas']['PaperlessSettingsResponse'];
type PaperlessSettingsWrite = components['schemas']['PaperlessSettingsWrite'];
type GnuCashSettingsWrite = components['schemas']['GnuCashSettingsWrite'];
type PaperlessStatusResponse = components['schemas']['PaperlessStatusResponse'];

export function useSettings() {
  const [appSettings, setAppSettings] = useState<ApplicationSettingsResponse | null>(null);
  const [paperlessSettings, setPaperlessSettings] = useState<PaperlessSettingsResponse | null>(null);
    const [paperlessStatus, setPaperlessStatus] = useState<PaperlessStatusResponse | null>(null);

  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchSettings = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [appRes, plRes, , plStatusRes] = await Promise.all([
        apiClient.GET('/api/v1/settings/application'),
        apiClient.GET('/api/v1/settings/paperless'),
        apiClient.GET('/api/v1/settings/gnucash'),
        apiClient.GET('/api/v1/paperless/status')
      ]);

      if (appRes.data) setAppSettings(appRes.data);
      if (plRes.data) setPaperlessSettings(plRes.data);
            if (plStatusRes.data) setPaperlessStatus(plStatusRes.data);
    } catch (err: any) {
      setError(err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSettings();
  }, [fetchSettings]);

  const updateAppSettings = async (data: ApplicationSettingsWrite) => {
    const res = await apiClient.PUT('/api/v1/settings/application', {
      body: data
    });
    if (res.data) setAppSettings(res.data);
    return res;
  };

  const updatePaperlessSettings = async (data: PaperlessSettingsWrite) => {
    const res = await apiClient.PUT('/api/v1/settings/paperless', {
      body: data
    });
    if (res.data) {
      setPaperlessSettings(res.data);
      // Refresh status after update
      const statusRes = await apiClient.GET('/api/v1/paperless/status');
      if (statusRes.data) setPaperlessStatus(statusRes.data);
    }
    return res;
  };

  const updateGnucashSettings = async (data: GnuCashSettingsWrite) => {
    const res = await apiClient.PUT('/api/v1/settings/gnucash', {
      body: data
    });
        return res;
  };

  return {
    appSettings,
    paperlessSettings,
    
    paperlessStatus,
    isLoading,
    error,
    updateAppSettings,
    updatePaperlessSettings,
    updateGnucashSettings,
    refresh: fetchSettings
  };
}
