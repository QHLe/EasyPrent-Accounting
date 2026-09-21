import React, { useState } from 'react';
import type { components } from '../../api/schema';
import { LinkedDocumentsPanel } from '../linked-documents';
import { AddressFields, type Address } from '../../components/AddressFields';

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
  const [altAddress, setAltAddress] = useState<Address>({
    street: initialData?.alternate_street || '',
    postal_code: initialData?.alternate_postal_code || '',
    city: initialData?.alternate_city || ''
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    try {
      await onSave({
        full_name: fullName,
        email: email || null,
        phone: phone || null,
        alternate_street: altAddress.street || null,
        alternate_postal_code: altAddress.postal_code || null,
        alternate_city: altAddress.city || null
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
          <AddressFields address={altAddress} onChange={setAltAddress} />
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
