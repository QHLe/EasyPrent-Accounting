import React, { useState, useRef } from 'react';
import { apiClient } from '../../api/client';
import { useGlobalMessages } from '../../app/AppShell';
import type { components } from '../../api/schema';

type ApplicationImportWrite = components['schemas']['ApplicationImportWrite'];

export function DataExportImport() {
  const [isExporting, setIsExporting] = useState(false);
  const [isImporting, setIsImporting] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { showMessage } = useGlobalMessages();

  const handleExport = async () => {
    setIsExporting(true);
    try {
      const res = await apiClient.GET('/api/v1/settings/export');
      if (res.data) {
        const json = JSON.stringify(res.data, null, 2);
        const blob = new Blob([json], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        const date = new Date().toISOString().split('T')[0];
        a.download = `easyprent-export-${date}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        showMessage({ type: 'success', text: 'Daten erfolgreich exportiert.' });
      }
    } catch (err: any) {
      showMessage({ type: 'error', text: `Export fehlgeschlagen: ${err.message || 'Unbekannter Fehler'}` });
    } finally {
      setIsExporting(false);
    }
  };

  const handleImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsImporting(true);
    try {
      const text = await file.text();
      const payload: ApplicationImportWrite = JSON.parse(text);
      
      const res = await apiClient.POST('/api/v1/settings/import', {
        body: payload
      });

      if (res.data) {
        showMessage({ 
          type: 'success', 
          text: `Import erfolgreich: ${res.data.row_count} Datensätze wiederhergestellt.` 
        });
        
      }
    } catch (err: any) {
      showMessage({ type: 'error', text: `Import fehlgeschlagen: ${err.message || 'Ungültiges Dateiformat'}` });
    } finally {
      setIsImporting(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  return (
    <div className="panel">
      <h3>Datensicherung</h3>
      <p>
        Sie können den aktuellen Datenbestand als Sicherungsdatei exportieren oder eine 
        bestehende Sicherung wiederherstellen. Konfigurierte Zugangsdaten (z. B. Paperless) 
        werden <strong>nicht</strong> exportiert.
      </p>
      
      <div className="actions" style={{ marginTop: '1rem', display: 'flex', gap: '1rem' }}>
        <button 
          onClick={handleExport} 
          disabled={isExporting || isImporting}
          className="button"
        >
          {isExporting ? 'Exportiert...' : 'Daten exportieren'}
        </button>

        <div>
          <input 
            type="file" 
            accept=".json,application/json" 
            ref={fileInputRef}
            onChange={handleImport}
            style={{ display: 'none' }}
            id="import-file-upload"
          />
          <button 
            onClick={() => fileInputRef.current?.click()}
            disabled={isExporting || isImporting}
            className="button button-outline"
          >
            {isImporting ? 'Importiert...' : 'Daten importieren'}
          </button>
        </div>
      </div>
    </div>
  );
}
