import React, { useState, useEffect } from 'react';
import { useSettings } from './useSettings';
import { DataExportImport } from './DataExportImport';
import { useGlobalMessages } from '../../app/AppShell';

export function SettingsView() {
  const { 
    appSettings, paperlessSettings, paperlessStatus, 
    updateAppSettings, updatePaperlessSettings, isLoading, error 
  } = useSettings();
  const { showMessage } = useGlobalMessages();

  const [showDelete, setShowDelete] = useState(false);
  const [plUrl, setPlUrl] = useState('');
  const [plToken, setPlToken] = useState('');
  const [isSavingApp, setIsSavingApp] = useState(false);
  const [isSavingPl, setIsSavingPl] = useState(false);

  useEffect(() => {
    if (appSettings) {
      setShowDelete(appSettings.show_delete_actions);
    }
    if (paperlessSettings) {
      setPlUrl(paperlessSettings.base_url || '');
      setPlToken(paperlessSettings.token_masked || '');
    }
  }, [appSettings, paperlessSettings]);

  const handleSaveApp = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSavingApp(true);
    try {
      await updateAppSettings({ show_delete_actions: showDelete });
      showMessage({ type: 'success', text: 'Allgemeine Einstellungen gespeichert.' });
    } catch (err: any) {
      showMessage({ type: 'error', text: `Fehler: ${err.message}` });
    } finally {
      setIsSavingApp(false);
    }
  };

  const handleSavePl = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSavingPl(true);
    try {
      await updatePaperlessSettings({ 
        base_url: plUrl, 
        // Only send token if it's not the masked string
        api_token: plToken && !plToken.includes('***') ? plToken : null 
      });
      showMessage({ type: 'success', text: 'Paperless-Einstellungen gespeichert.' });
    } catch (err: any) {
      showMessage({ type: 'error', text: `Fehler: ${err.message}` });
    } finally {
      setIsSavingPl(false);
    }
  };

  if (isLoading) return <div>Lade Einstellungen...</div>;
  if (error) return <div className="message error">Fehler beim Laden der Einstellungen: {error.message}</div>;

  return (
    <div className="settings-view">
      <h2>Einstellungen</h2>

      <div className="panel" style={{ marginBottom: '2rem' }}>
        <h3>Allgemein</h3>
        <form onSubmit={handleSaveApp}>
          <div className="form-group">
            <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <input 
                type="checkbox" 
                checked={showDelete}
                onChange={(e) => setShowDelete(e.target.checked)}
              />
              Löschaktionen in der Benutzeroberfläche anzeigen
            </label>
            <p className="hint" style={{ marginTop: '0.5rem' }}>
              Wenn deaktiviert, werden Archivierungs- und Lösch-Buttons ausgeblendet, um versehentliche Änderungen zu vermeiden.
            </p>
          </div>
          <div className="actions" style={{ marginTop: '1rem' }}>
            <button type="submit" className="button" disabled={isSavingApp}>
              {isSavingApp ? 'Speichere...' : 'Speichern'}
            </button>
          </div>
        </form>
      </div>

      <div className="panel" style={{ marginBottom: '2rem' }}>
        <h3>Paperless Integration</h3>
        <form onSubmit={handleSavePl}>
          <div className="form-group">
            <label htmlFor="plUrl">Base URL</label>
            <input 
              id="plUrl"
              type="url" 
              value={plUrl}
              onChange={(e) => setPlUrl(e.target.value)}
              placeholder="https://paperless.example.com"
              className="input"
            />
          </div>
          <div className="form-group">
            <label htmlFor="plToken">API Token</label>
            <input 
              id="plToken"
              type="text" 
              value={plToken}
              onChange={(e) => setPlToken(e.target.value)}
              placeholder="Token eingeben (maskiert beim Speichern)"
              className="input"
            />
            {paperlessSettings?.token_present && (
              <p className="hint">Ein Token ist bereits hinterlegt.</p>
            )}
          </div>
          
          {paperlessStatus && paperlessSettings?.base_url && (
            <div className={`message ${paperlessStatus.reachable ? 'success' : 'error'}`} style={{ marginTop: '1rem', padding: '0.5rem' }}>
              Status: {paperlessStatus.message}
            </div>
          )}

          <div className="actions" style={{ marginTop: '1rem' }}>
            <button type="submit" className="button" disabled={isSavingPl}>
              {isSavingPl ? 'Speichere...' : 'Speichern'}
            </button>
          </div>
        </form>
      </div>

      <DataExportImport />
    </div>
  );
}
