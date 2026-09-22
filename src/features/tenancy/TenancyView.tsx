import { useState } from 'react';
import { useTenancy } from './useTenancy';
import { TenantForm } from './TenantForm';
import { LeaseForm } from './LeaseForm';
import { useGlobalMessages } from '../../app/AppShell';
import { InlineListItem } from '../../components/InlineListItem';

export function TenancyView() {
  const { tenancy, isLoading, error, createTenant, updateTenant, deleteTenant, createLease, updateLease, deleteLease } = useTenancy();
  const { showMessage } = useGlobalMessages();

  const [activeTab, setActiveTab] = useState<'tenants' | 'leases'>('tenants');
  const [filterText, setFilterText] = useState('');
  
  const [isCreatingTenant, setIsCreatingTenant] = useState(false);
  const [editingTenantId, setEditingTenantId] = useState<number | null>(null);

  const [isCreatingLease, setIsCreatingLease] = useState(false);
  const [editingLeaseId, setEditingLeaseId] = useState<number | null>(null);

  if (isLoading) return <div>Lade Mieterdaten...</div>;
  if (error) return <div className="message error">Fehler: {error.message}</div>;

  const filteredTenants = tenancy?.tenants.filter(t => t.full_name.toLowerCase().includes(filterText.toLowerCase())) || [];
  const filteredLeases = tenancy?.leases.filter(l => 
    l.tenant_name?.toLowerCase().includes(filterText.toLowerCase()) || 
    l.unit_label?.toLowerCase().includes(filterText.toLowerCase())
  ) || [];

  const handleSaveTenant = async (data: any, id?: number) => {
    try {
      if (id) {
        await updateTenant(id, data);
        setEditingTenantId(null);
      } else {
        await createTenant(data);
        setIsCreatingTenant(false);
      }
      showMessage({ type: 'success', text: 'Mieter gespeichert.' });
    } catch (err: any) {
      showMessage({ type: 'error', text: `Fehler: ${err.message}` });
    }
  };

  const handleSaveLease = async (data: any, id?: number) => {
    try {
      if (id) {
        await updateLease(id, data);
        setEditingLeaseId(null);
      } else {
        await createLease(data);
        setIsCreatingLease(false);
      }
      showMessage({ type: 'success', text: 'Mietvertrag gespeichert.' });
    } catch (err: any) {
      showMessage({ type: 'error', text: `Fehler: ${err.message}` });
    }
  };

  const handleDeleteTenant = async (id: number) => {
    if (!window.confirm('Mieter wirklich löschen?')) return;
    try {
      await deleteTenant(id);
      showMessage({ type: 'success', text: 'Mieter gelöscht.' });
    } catch (err: any) {
      showMessage({ type: 'error', text: `Fehler: ${err.message}` });
    }
  };

  const handleDeleteLease = async (id: number) => {
    if (!window.confirm('Mietvertrag wirklich löschen?')) return;
    try {
      await deleteLease(id);
      showMessage({ type: 'success', text: 'Mietvertrag gelöscht.' });
    } catch (err: any) {
      showMessage({ type: 'error', text: `Fehler: ${err.message}` });
    }
  };

  return (
    <div className="tenancy-view">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
        <h2>Mieterverwaltung</h2>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <input 
            type="text" 
            placeholder="Suchen..." 
            value={filterText} 
            onChange={e => setFilterText(e.target.value)} 
            className="input"
          />
          {activeTab === 'tenants' ? (
            <button className="button" onClick={() => setIsCreatingTenant(true)}>Mieter erzeugen</button>
          ) : (
            <button className="button" onClick={() => setIsCreatingLease(true)}>Mietvertrag erzeugen</button>
          )}
        </div>
      </div>

      <div className="tabs" style={{ display: 'flex', gap: '1rem', marginBottom: '1rem', borderBottom: '1px solid #ddd', paddingBottom: '0.5rem' }}>
        <button 
          className={`button ${activeTab === 'tenants' ? '' : 'button-outline'}`}
          onClick={() => setActiveTab('tenants')}
        >
          Mieter
        </button>
        <button 
          className={`button ${activeTab === 'leases' ? '' : 'button-outline'}`}
          onClick={() => setActiveTab('leases')}
        >
          Mietverträge
        </button>
      </div>

      {activeTab === 'tenants' && (
        <div className="tenants-tab">
          {isCreatingTenant && (
            <div style={{ marginBottom: '1rem' }}>
              <TenantForm 
                onSave={(data) => handleSaveTenant(data)}
                onCancel={() => setIsCreatingTenant(false)}
              />
            </div>
          )}

          <div className="list">
            {filteredTenants.map(tenant => (
              <InlineListItem
                key={tenant.id}
                isEditing={editingTenantId === tenant.id}
                onEdit={() => setEditingTenantId(tenant.id)}
                renderDisplay={() => (
                  <>
                    <div>
                      <strong>{tenant.full_name}</strong>
                      <span style={{ marginLeft: '1rem', color: '#666' }}>{tenant.email || 'Keine E-Mail'}</span>
                    </div>
                    {editingTenantId !== tenant.id && (
                      <div style={{ display: 'flex', gap: '0.5rem' }}>

                        <button className="button button-small button-outline" onClick={() => handleDeleteTenant(tenant.id)}>Löschen</button>
                      </div>
                    )}
                  </>
                )}
                renderForm={() => (
                  <TenantForm 
                    initialData={tenant}
                    onSave={(data) => handleSaveTenant(data, tenant.id)}
                    onCancel={() => setEditingTenantId(null)}
                      />
                )}
              />
            ))}
            {filteredTenants.length === 0 && <p className="hint">Keine Mieter gefunden.</p>}
          </div>
        </div>
      )}

      {activeTab === 'leases' && (
        <div className="leases-tab">
          {isCreatingLease && (
            <div style={{ marginBottom: '1rem' }}>
              <LeaseForm 
                tenants={tenancy?.tenants || []}
                onSave={(data) => handleSaveLease(data)}
                onCancel={() => setIsCreatingLease(false)}
              />
            </div>
          )}

          <div className="list">
            {filteredLeases.map(lease => (
              <InlineListItem
                key={lease.id}
                isEditing={editingLeaseId === lease.id}
                onEdit={() => setEditingLeaseId(lease.id)}
                renderDisplay={() => (
                  <>
                    <div>
                      <strong>{lease.tenant_name}</strong>
                      <span style={{ marginLeft: '1rem', color: '#666' }}>
                        {lease.unit_label || 'Keine Wohnung'} | Kalt: {lease.rent_cold} €
                      </span>
                      <span className="tag" style={{ marginLeft: '1rem' }}>{lease.status === 'active' ? 'Aktiv' : 'Beendet'}</span>
                    </div>
                    {editingLeaseId !== lease.id && (
                      <div style={{ display: 'flex', gap: '0.5rem' }}>

                        <button className="button button-small button-outline" onClick={() => handleDeleteLease(lease.id)}>Löschen</button>
                      </div>
                    )}
                  </>
                )}
                renderForm={() => (
                  <LeaseForm 
                    initialData={lease}
                    tenants={tenancy?.tenants || []}
                    onSave={(data) => handleSaveLease(data, lease.id)}
                    onCancel={() => setEditingLeaseId(null)}
                      />
                )}
              />
            ))}
            {filteredLeases.length === 0 && <p className="hint">Keine Mietverträge gefunden.</p>}
          </div>
        </div>
      )}
    </div>
  );
}
