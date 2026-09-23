import React, { useCallback, useEffect, useState } from 'react';
import { apiClient } from '../../api/client';
import type { components } from '../../api/schema';
import { LinkedDocumentsPanel } from '../linked-documents';
import { useAssetRegistry } from '../asset-registry';

type LeaseWrite = components['schemas']['LeaseWrite'];
type LeaseResponse = components['schemas']['LeaseResponse'];
type TenantResponse = components['schemas']['TenantResponse'];
type GnuCashAccount = components['schemas']['GnuCashAccountResponse'];

interface Props {
  initialData?: LeaseResponse;
  tenants: TenantResponse[];
  onSave: (data: LeaseWrite) => Promise<void>;
  onCancel: () => void;
}

export function LeaseForm({ initialData, tenants, onSave, onCancel }: Props) {
  const { assets } = useAssetRegistry();
  const [isSaving, setIsSaving] = useState(false);
  
  const [tenantId, setTenantId] = useState<number | ''>(initialData?.tenant_id || '');
  const [unitId, setUnitId] = useState<number | ''>(initialData?.unit_id || '');
    const [roomId, setRoomId] = useState<number | ''>(initialData?.room_id || '');

  React.useEffect(() => {
    if (roomId !== '') {
      const room = assets?.rooms.find(r => r.id === roomId);
      if (room && room.unit_id !== unitId) {
        setUnitId(room.unit_id);
      }
    }
  }, [roomId, assets]);
  const [rentCold, setRentCold] = useState(initialData?.rent_cold || '');
  const [advance, setAdvance] = useState(initialData?.additional_charges_advance || '');
  const [occupants, setOccupants] = useState<number>(initialData?.occupant_count || 1);
  const [startDate, setStartDate] = useState(initialData?.start_date || '');
  const [endDate, setEndDate] = useState(initialData?.end_date || '');
  const [status, setStatus] = useState(initialData?.status || 'active');
  const [accountGuid, setAccountGuid] = useState(initialData?.gnucash_nk_account_guid || '');
  const [accounts, setAccounts] = useState<GnuCashAccount[]>([]);
  const [accountsLoading, setAccountsLoading] = useState(true);
  const [accountError, setAccountError] = useState<string | null>(null);

  const loadAccounts = useCallback(async () => {
    setAccountsLoading(true);
    setAccountError(null);
    try {
      const settings = await apiClient.GET('/api/v1/settings/gnucash');
      if (!settings.data) throw new Error('Verbindungseinstellungen konnten nicht geladen werden.');
      if (!settings.data.configured) {
        setAccounts([]);
        setAccountError('GnuCash-Verbindung ist nicht eingerichtet. Bitte unter Einstellungen hinterlegen.');
        return;
      }
      const response = await apiClient.GET('/api/v1/settings/gnucash/accounts');
      if (!response.data) throw new Error('Konten konnten nicht geladen werden.');
      setAccounts(response.data);
    } catch (cause) {
      setAccountError(
        'GnuCash-Konten konnten nicht geladen werden: ' +
        (cause instanceof Error ? cause.message : String(cause)),
      );
    } finally {
      setAccountsLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadAccounts();
  }, [loadAccounts]);
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    try {
      await onSave({
        tenant_id: tenantId as number,
        unit_id: unitId === '' ? null : (unitId as number),
        room_id: roomId === '' ? null : (roomId as number),
        rent_cold: rentCold,
        additional_charges_advance: advance,
        occupant_count: occupants,
        start_date: startDate,
        end_date: endDate || null,
        status,
        gnucash_nk_account_guid: accountGuid || null,
        gnucash_nk_account_name: accountGuid
          ? accounts.find(account => account.guid === accountGuid)?.full_name
            || (accountGuid === initialData?.gnucash_nk_account_guid
              ? initialData?.gnucash_nk_account_name : null)
            || null
          : null,
      });
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="panel inline-edit">
      <h4>{initialData ? 'Mietvertrag bearbeiten' : 'Mietvertrag anlegen'}</h4>
      <form onSubmit={handleSubmit}>
        <div className="form-group-row" style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
          <div className="form-group" style={{ flex: 1 }}>
            <label>Mieter</label>
            <select required value={tenantId} onChange={e => setTenantId(Number(e.target.value))} className="input">
              <option value="">-- Bitte wählen --</option>
              {tenants.map(t => <option key={t.id} value={t.id}>{t.full_name}</option>)}
            </select>
          </div>
          <div className="form-group" style={{ flex: 1 }}>
            <label>Wohnung</label>
            <select value={unitId} onChange={e => setUnitId(e.target.value ? Number(e.target.value) : '')} className="input">
              <option value="">-- Keine --</option>
              {assets?.units.map(u => <option key={u.id} value={u.id}>{u.label}</option>)}
            </select>
          </div>
          <div className="form-group" style={{ flex: 1 }}>
            <label>Zimmer (Optional)</label>
            <select value={roomId} onChange={e => setRoomId(e.target.value ? Number(e.target.value) : '')} className="input">
              <option value="">-- Kein --</option>
              {assets?.rooms.filter(r => r.unit_id === unitId || !unitId).map(r => <option key={r.id} value={r.id}>{r.label}</option>)}
            </select>
          </div>
        </div>

        <div className="form-group-row" style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap', marginTop: '1rem' }}>
          <div className="form-group" style={{ flex: 1 }}>
            <label>Kaltmiete</label>
            <input required type="number" step="0.01" value={rentCold} onChange={e => setRentCold(e.target.value)} className="input" />
          </div>
          <div className="form-group" style={{ flex: 1 }}>
            <label>Nebenkostenvorauszahlung</label>
            <input required type="number" step="0.01" value={advance} onChange={e => setAdvance(e.target.value)} className="input" />
          </div>
          <div className="form-group" style={{ flex: 1 }}>
            <label>Personenzahl</label>
            <input required type="number" min="1" value={occupants} onChange={e => setOccupants(Number(e.target.value))} className="input" />
          </div>
        </div>

        <div className="form-group-row" style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap', marginTop: '1rem' }}>
          <div className="form-group" style={{ flex: 1 }}>
            <label>Startdatum</label>
            <input required type="date" value={startDate} onChange={e => setStartDate(e.target.value)} className="input" />
          </div>
          <div className="form-group" style={{ flex: 1 }}>
            <label>Enddatum (Optional)</label>
            <input type="date" value={endDate} onChange={e => setEndDate(e.target.value)} className="input" />
          </div>
          <div className="form-group" style={{ flex: 1 }}>
            <label>Status</label>
            <select value={status} onChange={e => setStatus(e.target.value)} className="input">
              <option value="active">Aktiv</option>
              <option value="terminated">Beendet</option>
            </select>
          </div>
        </div>

        <div className="form-group" style={{ marginTop: '1rem' }}>
          <label htmlFor="leaseGnuCashAccount">GnuCash-NK-Vorauszahlungskonto (optional)</label>
          <select
            id="leaseGnuCashAccount"
            className="input"
            value={accountGuid}
            onChange={event => setAccountGuid(event.target.value)}
            aria-describedby={accountError ? 'leaseGnuCashError' : undefined}
          >
            <option value="">Kein Konto zugeordnet</option>
            {accountGuid && !accounts.some(account => account.guid === accountGuid) && (
              <option value={accountGuid}>
                {initialData?.gnucash_nk_account_name || accountGuid} (derzeit nicht verfügbar)
              </option>
            )}
            {accounts.map(account => (
              <option key={account.guid} value={account.guid}>
                {account.full_name || account.name}
              </option>
            ))}
          </select>
          {accountsLoading && <p className="hint">GnuCash-Konten werden geladen...</p>}
          {accountError && (
            <div id="leaseGnuCashError" className="message error" role="alert">
              {accountError}{' '}
              <button type="button" className="button button-small button-outline" onClick={() => void loadAccounts()}>
                Erneut versuchen
              </button>
            </div>
          )}
          {!accountsLoading && !accountError && accounts.length === 0 && (
            <p className="hint">Keine GnuCash-Konten gefunden.</p>
          )}
        </div>

        <div className="actions" style={{ display: 'flex', gap: '1rem', marginTop: '1rem' }}>
          <button type="submit" className="button" disabled={isSaving}>Speichern</button>
          <button type="button" className="button button-outline" onClick={onCancel} disabled={isSaving}>Abbrechen</button>
        </div>
      </form>
      
      {initialData?.id && (
        <div style={{ marginTop: '2rem' }}>
          <LinkedDocumentsPanel ownerType="leases" ownerId={initialData.id} />
        </div>
      )}
    </div>
  );
}
