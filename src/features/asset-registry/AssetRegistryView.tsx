import React, { useState } from 'react';
import { useAssetRegistry } from './useAssetRegistry';
import { AssetForm, AssetType } from './AssetForm';
import { useGlobalMessages } from '../../app/AppShell';
import { useSettings } from '../settings/useSettings';

export function AssetRegistryView() {
  const { assets, isLoading, error, createProperty, createBuilding, createUnit, createRoom, updateProperty, updateBuilding, updateUnit, updateRoom, archiveProperty, archiveBuilding, archiveUnit, archiveRoom, deleteProperty, deleteBuilding, deleteUnit, deleteRoom, restoreAsset } = useAssetRegistry();
  const { appSettings } = useSettings();
  const { showMessage } = useGlobalMessages();

  const showDelete = appSettings?.show_delete_actions ?? false;

  const [creatingType, setCreatingType] = useState<AssetType | null>(null);
  const [editingItem, setEditingItem] = useState<{ type: AssetType; data: any } | null>(null);

  if (isLoading) return <div>Lade Objekte...</div>;
  if (error) return <div className="message error">Fehler beim Laden: {error.message}</div>;

  const handleSave = async (type: AssetType, data: any) => {
    try {
      if (editingItem) {
        if (type === 'property') await updateProperty(editingItem.data.id, data);
        if (type === 'building') await updateBuilding(editingItem.data.id, data);
        if (type === 'unit') await updateUnit(editingItem.data.id, data);
        if (type === 'room') await updateRoom(editingItem.data.id, data);
        showMessage({ type: 'success', text: 'Änderungen gespeichert.' });
        setEditingItem(null);
      } else {
        if (type === 'property') await createProperty(data);
        if (type === 'building') await createBuilding(data);
        if (type === 'unit') await createUnit(data);
        if (type === 'room') await createRoom(data);
        showMessage({ type: 'success', text: 'Objekt erstellt.' });
        setCreatingType(null);
      }
    } catch (err: any) {
      showMessage({ type: 'error', text: `Fehler: ${err.message}` });
    }
  };

  const handleArchive = async (type: AssetType, id: number) => {
    try {
      if (type === 'property') await archiveProperty(id);
      if (type === 'building') await archiveBuilding(id);
      if (type === 'unit') await archiveUnit(id);
      if (type === 'room') await archiveRoom(id);
      showMessage({ type: 'success', text: 'Objekt archiviert.' });
    } catch (err: any) {
      showMessage({ type: 'error', text: `Fehler: ${err.message}` });
    }
  };

  const handleDelete = async (type: AssetType, id: number) => {
    if (!window.confirm('Wirklich löschen?')) return;
    try {
      if (type === 'property') await deleteProperty(id);
      if (type === 'building') await deleteBuilding(id);
      if (type === 'unit') await deleteUnit(id);
      if (type === 'room') await deleteRoom(id);
      showMessage({ type: 'success', text: 'Objekt gelöscht.' });
    } catch (err: any) {
      showMessage({ type: 'error', text: `Fehler: ${err.message}` });
    }
  };

  const handleRestore = async (type: AssetType, id: number) => {
    try {
      await restoreAsset(type, id);
      showMessage({ type: 'success', text: 'Objekt wiederhergestellt.' });
    } catch (err: any) {
      showMessage({ type: 'error', text: `Fehler: ${err.message}` });
    }
  };

  const renderActions = (type: AssetType, item: any) => {
    return (
      <div style={{ display: 'flex', gap: '0.5rem' }}>
        <button className="button button-small" onClick={() => setEditingItem({ type, data: item })}>
          Bearbeiten
        </button>
        {item.is_archived ? (
          <>
            <button className="button button-small button-outline" onClick={() => handleRestore(type, item.id)}>
              Wiederherstellen
            </button>
            {showDelete && (
              <button className="button button-small button-outline" onClick={() => handleDelete(type, item.id)}>
                Löschen
              </button>
            )}
          </>
        ) : (
          <button className="button button-small button-outline" onClick={() => handleArchive(type, item.id)}>
            Archivieren
          </button>
        )}
      </div>
    );
  };

  const renderItemRow = (type: AssetType, item: any, title: string, details: string, paddingLeft: number = 0) => {
    const isEditing = editingItem?.type === type && editingItem?.data.id === item.id;
    return (
      <div key={`${type}-${item.id}`} style={{ paddingLeft: `${paddingLeft}rem`, marginBottom: '0.5rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.5rem', backgroundColor: item.is_archived ? '#f9f9f9' : '#fff', border: '1px solid #eee', borderRadius: '4px' }}>
          <div>
            <strong>{title}</strong>
            <span style={{ marginLeft: '1rem', color: '#666', fontSize: '0.9em' }}>{details}</span>
            {item.is_archived && <span className="tag" style={{ marginLeft: '0.5rem' }}>Archiviert</span>}
          </div>
          {!isEditing && renderActions(type, item)}
        </div>
        {isEditing && (
          <div style={{ marginTop: '0.5rem' }}>
            <AssetForm 
              type={type} 
              initialData={item} 
              onSave={handleSave} 
              onCancel={() => setEditingItem(null)}
              properties={assets?.properties}
              buildings={assets?.buildings}
              units={assets?.units}
            />
          </div>
        )}
      </div>
    );
  };

  // Grouping logic for the hierarchical tree
  // Tree: Properties -> Buildings -> Units -> Rooms
  // Also need to show orphaned buildings, units, rooms at the top level
  
  return (
    <div className="asset-registry-view">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
        <h2>Objektverwaltung</h2>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <select 
            className="input" 
            value={creatingType || ''} 
            onChange={e => setCreatingType(e.target.value as AssetType)}
          >
            <option value="">-- Objekt erzeugen --</option>
            <option value="property">Anlage erzeugen</option>
            <option value="building">Gebäude erzeugen</option>
            <option value="unit">Wohnung erzeugen</option>
            <option value="room">Zimmer erzeugen</option>
          </select>
        </div>
      </div>

      {creatingType && (
        <div style={{ marginBottom: '2rem' }}>
          <AssetForm 
            type={creatingType} 
            onSave={handleSave} 
            onCancel={() => setCreatingType(null)} 
            properties={assets?.properties}
            buildings={assets?.buildings}
            units={assets?.units}
          />
        </div>
      )}

      <div className="asset-list">
        {/* Render Properties and their children */}
        {assets?.properties.map(p => (
          <div key={`p-${p.id}`}>
            {renderItemRow('property', p, p.name, `${p.street}, ${p.city}`)}
            
            {/* Buildings inside property */}
            {assets.buildings.filter(b => b.property_id === p.id).map(b => (
              <div key={`b-${b.id}`}>
                {renderItemRow('building', b, `Gebäude: ${b.name}`, `${b.street}, ${b.city}`, 2)}
                
                {/* Units inside building */}
                {assets.units.filter(u => u.building_id === b.id).map(u => (
                  <div key={`u-${u.id}`}>
                    {renderItemRow('unit', u, `Wohnung: ${u.label}`, `${u.area_sqm} qm, ${u.room_count} Zimmer`, 4)}
                    
                    {/* Rooms inside unit */}
                    {assets.rooms.filter(r => r.unit_id === u.id).map(r => (
                      <React.Fragment key={`r-${r.id}`}>
                        {renderItemRow('room', r, `Zimmer: ${r.label}`, r.area_sqm ? `${r.area_sqm} qm` : '', 6)}
                      </React.Fragment>
                    ))}
                  </div>
                ))}
              </div>
            ))}
          </div>
        ))}

        {/* Render orphaned Buildings */}
        {assets?.buildings.filter(b => !b.property_id).map(b => (
          <div key={`ob-${b.id}`}>
            {renderItemRow('building', b, `Gebäude: ${b.name}`, `${b.street}, ${b.city}`)}
            
            {assets.units.filter(u => u.building_id === b.id).map(u => (
              <div key={`ou-${u.id}`}>
                {renderItemRow('unit', u, `Wohnung: ${u.label}`, `${u.area_sqm} qm, ${u.room_count} Zimmer`, 2)}
                
                {assets.rooms.filter(r => r.unit_id === u.id).map(r => (
                  <React.Fragment key={`or-${r.id}`}>
                    {renderItemRow('room', r, `Zimmer: ${r.label}`, r.area_sqm ? `${r.area_sqm} qm` : '', 4)}
                  </React.Fragment>
                ))}
              </div>
            ))}
          </div>
        ))}

        {/* Render orphaned Units */}
        {assets?.units.filter(u => !u.building_id).map(u => (
          <div key={`oou-${u.id}`}>
            {renderItemRow('unit', u, `Wohnung: ${u.label}`, `${u.area_sqm} qm, ${u.room_count} Zimmer`)}
            
            {assets.rooms.filter(r => r.unit_id === u.id).map(r => (
              <React.Fragment key={`oor-${r.id}`}>
                {renderItemRow('room', r, `Zimmer: ${r.label}`, r.area_sqm ? `${r.area_sqm} qm` : '', 2)}
              </React.Fragment>
            ))}
          </div>
        ))}

        {/* Render orphaned Rooms (though they require a unit, just in case) */}
        {assets?.rooms.filter(r => !assets.units.find(u => u.id === r.unit_id)).map(r => (
          <React.Fragment key={`ooor-${r.id}`}>
            {renderItemRow('room', r, `Zimmer: ${r.label} (Wohnung nicht gefunden)`, r.area_sqm ? `${r.area_sqm} qm` : '')}
          </React.Fragment>
        ))}
      </div>
    </div>
  );
}
