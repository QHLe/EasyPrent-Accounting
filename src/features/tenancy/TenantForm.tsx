import React, { useState } from 'react';
import type { components } from '../../api/schema';
import { LinkedDocumentsPanel } from '../linked-documents';

type TenantWrite = components['schemas']['TenantWrite'];

interface Props {
  initialData?: any;
  onSave: (data: TenantWrite) => Promise<void>;
  onCancel: () => void;
}

export function TenantForm({ initialData, onSave, onCancel }: Props) {
  const [isSaving, setIsSaving] = useState(false);
  
  const [fullName, setFullName] = useState(initialData?.full_name || '');
  const [email, setEmail] = useState(initialData?.email || '');
  const [phone, setPhone] = useState(initialData?.phone || '');
  const [street, setStreet] = useState(initialData?.alternate_street || '');
  const [postal, setPostal] = useState(initialData?.alternate_postal_code || '');
  const [city, setCity] = useState(initialData?.alternate_city || '');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    try {
      await onSave({
        full_name: fullName,
        email: email || null,
        phone: phone || null,
        alternate_street: street || null,
        alternate_postal_code: postal || null,
        alternate_city: city || null
      });
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="panel inline-edit">
      <h4>{initialData ? 'Mieter bearbeiten' : 'Mieter anlegen'}</h4>
      <form onSubmit={handleSubmit}>
        <div className="form-group-row" style={{ display: 'flex', gap: '1rem' }}>
          <div className="form-group" style={{ flex: 1 }}>
            <label>Vollständiger Name</label>
            <input required type="text" value={fullName} onChange={e => setFullName(e.target.value)} className="input" />
          </div>
          <div className="form-group" style={{ flex: 1 }}>
            <label>E-Mail (Optional)</label>
            <input type="email" value={email} onChange={e => setEmail(e.target.value)} className="input" />
          </div>
          <div className="form-group" style={{ flex: 1 }}>
            <label>Telefon (Optional)</label>
            <input type="text" value={phone} onChange={e => setPhone(e.target.value)} className="input" />
          </div>
        </div>

        <fieldset style={{ marginTop: '1rem', border: '1px solid #ddd', padding: '1rem' }}>
          <legend>Abweichende Anschrift (Optional)</legend>
          <div className="form-group-row" style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
            <div className="form-group" style={{ flex: 1 }}>
              <label>Straße</label>
              <input type="text" value={street} onChange={e => setStreet(e.target.value)} className="input" />
            </div>
            <div className="form-group" style={{ flex: 1 }}>
              <label>PLZ</label>
              <input type="text" value={postal} onChange={e => setPostal(e.target.value)} className="input" />
            </div>
            <div className="form-group" style={{ flex: 1 }}>
              <label>Stadt</label>
              <input type="text" value={city} onChange={e => setCity(e.target.value)} className="input" />
            </div>
          </div>
        </fieldset>

        <div className="actions" style={{ display: 'flex', gap: '1rem', marginTop: '1rem' }}>
          <button type="submit" className="button" disabled={isSaving}>Speichern</button>
          <button type="button" className="button button-outline" onClick={onCancel} disabled={isSaving}>Abbrechen</button>
        </div>
      </form>
      
      {initialData?.id && (
        <div style={{ marginTop: '2rem' }}>
          <LinkedDocumentsPanel ownerType="tenants" ownerId={initialData.id} />
        </div>
      )}
    </div>
  );
}
