import React, { useState } from 'react';
import type { components } from '../../api/schema';
import { AddressFields, type Address } from '../../components/AddressFields';

type PropertyWrite = components['schemas']['PropertyWrite'];
type BuildingWrite = components['schemas']['BuildingWrite'];
type UnitWrite = components['schemas']['UnitWrite'];
type RoomWrite = components['schemas']['RoomWrite'];

export type AssetType = 'property' | 'building' | 'unit' | 'room';

interface Props {
  type: AssetType;
  initialData?: any;
  onSave: (type: AssetType, data: any) => Promise<void>;
  onCancel: () => void;
  // Options for dropdowns
  properties?: any[];
  buildings?: any[];
  units?: any[];
}

export function AssetForm({ type, initialData, onSave, onCancel, properties = [], buildings = [], units = [], organizationId = 1 }: Props & { organizationId?: number }) {
  const [isSaving, setIsSaving] = useState(false);
  
  // Property state
  const [name, setName] = useState(initialData?.name || '');
  const [address, setAddress] = useState<Address>({
    street: initialData?.street || '',
    city: initialData?.city || '',
    postal_code: initialData?.postal_code || ''
  });

  // Building state
  const [propertyId, setPropertyId] = useState<number | ''>(initialData?.property_id || '');
  const [yearBuilt] = useState<number | ''>(initialData?.year_built || '');
  
  // Unit state
  const [buildingId, setBuildingId] = useState<number | ''>(initialData?.building_id || '');
  const [label, setLabel] = useState(initialData?.label || '');
  const [area, setArea] = useState(initialData?.area_sqm || '');
  const [mea, setMea] = useState(initialData?.mea_percent || '0');
  const [roomCount, setRoomCount] = useState<number>(initialData?.room_count || 1);

  // Room state
  const [unitId, setUnitId] = useState<number | ''>(initialData?.unit_id || '');
  const [roomArea, setRoomArea] = useState(initialData?.area_sqm || '');
  const [roomShare, setRoomShare] = useState(initialData?.area_share_percent || '');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    try {
      if (type === 'property') {
        const payload: PropertyWrite = { organization_id: initialData?.organization_id || organizationId, name, street: address.street, city: address.city, postal_code: address.postal_code };
        await onSave(type, payload);
      } else if (type === 'building') {
        const payload: BuildingWrite = { property_id: propertyId === '' ? null : propertyId, name, street: address.street, city: address.city, postal_code: address.postal_code, year_built: yearBuilt === '' ? null : yearBuilt };
        await onSave(type, payload);
      } else if (type === 'unit') {
        const payload: UnitWrite = { building_id: buildingId === '' ? null : buildingId, label, area_sqm: area, mea_percent: mea, room_count: roomCount, street: address.street || null, city: address.city || null, postal_code: address.postal_code || null };
        await onSave(type, payload);
      } else if (type === 'room') {
        const payload: RoomWrite = { unit_id: unitId as number, label, area_sqm: roomArea || null, area_share_percent: roomShare || null };
        await onSave(type, payload);
      }
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="panel inline-edit">
      <h4>{initialData ? 'Bearbeiten' : 'Erstellen'}</h4>
      <form onSubmit={handleSubmit}>
        
        {/* Fields for Property & Building */}
        {(type === 'property' || type === 'building') && (
          <div className="form-group">
            <label>Name</label>
            <input required type="text" value={name} onChange={e => setName(e.target.value)} className="input" />
          </div>
        )}

        {/* Addresses */}
        {(type === 'property' || type === 'building' || type === 'unit') && (
          <AddressFields 
            address={address} 
            onChange={setAddress} 
            required={type !== 'unit'} 
          />
        )}

        {/* Property ID for Building */}
        {type === 'building' && (
          <div className="form-group">
            <label>Zugehörige Anlage (Optional)</label>
            <select value={propertyId} onChange={e => setPropertyId(e.target.value ? Number(e.target.value) : '')} className="input">
              <option value="">-- Keine Anlage --</option>
              {properties.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </div>
        )}

        {/* Building ID for Unit */}
        {type === 'unit' && (
          <div className="form-group">
            <label>Zugehöriges Gebäude (Optional)</label>
            <select value={buildingId} onChange={e => setBuildingId(e.target.value ? Number(e.target.value) : '')} className="input">
              <option value="">-- Kein Gebäude --</option>
              {buildings.map(b => <option key={b.id} value={b.id}>{b.name}</option>)}
            </select>
          </div>
        )}

        {/* Unit & Room shared fields */}
        {(type === 'unit' || type === 'room') && (
          <div className="form-group">
            <label>Bezeichnung (Label)</label>
            <input required type="text" value={label} onChange={e => setLabel(e.target.value)} className="input" />
          </div>
        )}

        {/* Unit fields */}
        {type === 'unit' && (
          <div className="form-group-row" style={{ display: 'flex', gap: '1rem' }}>
            <div className="form-group" style={{ flex: 1 }}>
              <label>Fläche (qm)</label>
              <input required type="number" step="0.01" value={area} onChange={e => setArea(e.target.value)} className="input" />
            </div>
            <div className="form-group" style={{ flex: 1 }}>
              <label>Miteigentumsanteil (%)</label>
              <input required type="number" step="0.01" value={mea} onChange={e => setMea(e.target.value)} className="input" />
            </div>
            <div className="form-group" style={{ flex: 1 }}>
              <label>Zimmeranzahl</label>
              <input required type="number" value={roomCount} onChange={e => setRoomCount(Number(e.target.value))} className="input" />
            </div>
          </div>
        )}

        {/* Room fields */}
        {type === 'room' && (
          <>
            <div className="form-group">
              <label>Zugehörige Wohnung</label>
              <select required value={unitId} onChange={e => setUnitId(Number(e.target.value))} className="input">
                <option value="">-- Bitte wählen --</option>
                {units.map(u => <option key={u.id} value={u.id}>{u.label} {u.building_name ? `(${u.building_name})` : ''}</option>)}
              </select>
            </div>
            <div className="form-group-row" style={{ display: 'flex', gap: '1rem' }}>
              <div className="form-group" style={{ flex: 1 }}>
                <label>Fläche (qm, Optional)</label>
                <input type="number" step="0.01" value={roomArea} onChange={e => setRoomArea(e.target.value)} className="input" />
              </div>
              <div className="form-group" style={{ flex: 1 }}>
                <label>Flächenanteil (%, Optional)</label>
                <input type="number" step="0.01" value={roomShare} onChange={e => setRoomShare(e.target.value)} className="input" />
              </div>
            </div>
          </>
        )}

        <div className="actions" style={{ display: 'flex', gap: '1rem', marginTop: '1rem' }}>
          <button type="submit" className="button" disabled={isSaving}>Speichern</button>
          <button type="button" className="button button-outline" onClick={onCancel} disabled={isSaving}>Abbrechen</button>
        </div>
      </form>
    </div>
  );
}
