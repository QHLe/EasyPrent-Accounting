import { useEffect, useState } from 'react';
import { apiClient } from '../api/client';

/** Hide destructive controls until the application setting has been loaded. */
export function useDeleteActions(): boolean {
  const [enabled, setEnabled] = useState(false);

  useEffect(() => {
    let active = true;
    void apiClient.GET('/api/v1/settings/application')
      .then(response => {
        if (active) setEnabled(response.data?.show_delete_actions === true);
      })
      .catch(() => {
        if (active) setEnabled(false);
      });
    return () => { active = false; };
  }, []);

  return enabled;
}
