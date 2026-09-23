import React, { useState, useEffect } from 'react';
import { useSettings } from './useSettings';
import { DataExportImport } from './DataExportImport';
import { useGlobalMessages } from '../../app/AppShell';

export function SettingsView() {
  const { 
    appSettings, paperlessSettings, paperlessStatus, gnucashSettings,
    updateAppSettings, updatePaperlessSettings, updateGnucashSettings, isLoading, error
  } = useSettings();
  const { showMessage } = useGlobalMessages();

  const [showDelete, setShowDelete] = useState(false);
  const [plUrl, setPlUrl] = useState('');
  const [plToken, setPlToken] = useState('');
  const [isSavingApp, setIsSavingApp] = useState(false);
  const [isSavingPl, setIsSavingPl] = useState(false);
  const [gcHost, setGcHost] = useState('');
  const [gcPort, setGcPort] = useState('5432');
  const [gcDatabase, setGcDatabase] = useState('');
  const [gcUsername, setGcUsername] = useState('');
  const [gcPassword, setGcPassword] = useState('');
  const [gcSslmode, setGcSslmode] = useState('require');
  const [isSavingGc, setIsSavingGc] = useState(false);

  useEffect(() => {
    if (appSettings) {
      setShowDelete(appSettings.show_delete_actions);
    }
    if (paperlessSettings) {
      setPlUrl(paperlessSettings.base_url || '');
      setPlToken(paperlessSettings.token_masked || '');
    }
  }, [appSettings, paperlessSettings]);

  useEffect(() => {
    if (!gnucashSettings) return;
    setGcHost(gnucashSettings.host);
    setGcPort(String(gnucashSettings.port));
    setGcDatabase(gnucashSettings.database);
    setGcUsername(gnucashSettings.username);
    setGcPassword('');
    setGcSslmode(gnucashSettings.sslmode);
  }, [gnucashSettings]);

  const handleSaveGc = async (event: React.FormEvent) => {
    event.preventDefault();
    setIsSavingGc(true);
    try {
      await updateGnucashSettings({
        host: gcHost,
        port: Number(gcPort),
        database: gcDatabase,
        username: gcUsername,
        password: gcPassword || null,
        sslmode: gcSslmode,
      });
      showMessage({ type: 'success', text: 'GnuCash-Verbindung gespeichert.' });
    } catch (cause) {
      showMessage({
        type: 'error',
        text: 'GnuCash-Verbindung konnte nicht gespeichert werden: ' + (cause instanceof Error ? cause.message : String(cause)),
      });
    } finally {
      setIsSavingGc(false);
    }
  };

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

      <div className="panel" style={{ marginBottom: '2rem' }}>
        <h3>GnuCash-Verbindung</h3>
        <p className="hint">
          Diese Verbindung wird für die Auswahl des NK-Vorauszahlungskontos im Mietvertrag verwendet.
        </p>
        <form onSubmit={handleSaveGc}>
          <div className="form-group-row" style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
            <div className="form-group" style={{ flex: 1 }}>
              <label htmlFor="gcHost">Host</label>
              <input id="gcHost" required value={gcHost} onChange={event => setGcHost(event.target.value)} className="input" />
            </div>
            <div className="form-group" style={{ flex: 1 }}>
              <label htmlFor="gcPort">Port</label>
              <input id="gcPort" required type="number" min="1" max="65535" value={gcPort} onChange={event => setGcPort(event.target.value)} className="input" />
            </div>
          </div>
          <div className="form-group-row" style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
            <div className="form-group" style={{ flex: 1 }}>
              <label htmlFor="gcDatabase">Datenbank</label>
              <input id="gcDatabase" required value={gcDatabase} onChange={event => setGcDatabase(event.target.value)} className="input" />
            </div>
            <div className="form-group" style={{ flex: 1 }}>
              <label htmlFor="gcUsername">Benutzername</label>
              <input id="gcUsername" required value={gcUsername} onChange={event => setGcUsername(event.target.value)} className="input" />
            </div>
          </div>
          <div className="form-group-row" style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
            <div className="form-group" style={{ flex: 1 }}>
              <label htmlFor="gcPassword">Passwort</label>
              <input
                id="gcPassword"
                type="password"
                required={!gnucashSettings?.password_present}
                value={gcPassword}
                onChange={event => setGcPassword(event.target.value)}
                autoComplete="new-password"
                className="input"
              />
              {gnucashSettings?.password_present && (
                <p className="hint">Passwort ist hinterlegt. Leer lassen, um es beizubehalten.</p>
              )}
            </div>
            <div className="form-group" style={{ flex: 1 }}>
              <label htmlFor="gcSslmode">SSL-Modus</label>
              <select id="gcSslmode" value={gcSslmode} onChange={event => setGcSslmode(event.target.value)} className="input">
                <option value="disable">disable</option>
                <option value="allow">allow</option>
                <option value="prefer">prefer</option>
                <option value="require">require</option>
                <option value="verify-ca">verify-ca</option>
                <option value="verify-full">verify-full</option>
              </select>
            </div>
          </div>
          <div className="actions" style={{ marginTop: '1rem' }}>
            <button type="submit" className="button" disabled={isSavingGc}>
              {isSavingGc ? 'Speichere...' : 'GnuCash-Verbindung speichern'}
            </button>
          </div>
        </form>
      </div>

      <DataExportImport />
    </div>
  );
}
