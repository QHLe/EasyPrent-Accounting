import React, { useState } from 'react';
import { useAssetRegistry } from './useAssetRegistry';
import { AssetForm, AssetType } from './AssetForm';
import { useGlobalMessages } from '../../app/AppShell';
import { useSettings } from '../settings/useSettings';
import { InlineListItem } from '../../components/InlineListItem';

export function AssetRegistryView() {
  const { assets, isLoading, error, createProperty, createBuilding, createUnit, createRoom, updateProperty, updateBuilding, updateUnit, updateRoom, archiveProperty, archiveBuilding, archiveUnit, archiveRoom, deleteProperty, deleteBuilding, deleteUnit, deleteRoom, restoreAsset } = useAssetRegistry();
  const { appSettings } = useSettings();
  const { showMessage } = useGlobalMessages();

  const showDelete = appSettings?.show_delete_actions ?? false;

  const [creatingType, setCreatingType] = useState<AssetType | null>(null);
  const [editingItem, setEditingItem] = useState<{ type: AssetType; data: any } | null>(null);
  const [filterText, setFilterText] = useState('');

  if (isLoading) return <div>Lade Objekte...</div>;
  if (error) return <div className="message error">Fehler beim Laden: {error.message}</div>;

  const handleSave = async (type: AssetType, data: any) => {
    try {
      if (editingItem) {
        const updateFns = { property: updateProperty, building: updateBuilding, unit: updateUnit, room: updateRoom };
        await updateFns[type](editingItem.data.id, data);
        showMessage({ type: 'success', text: 'Änderungen gespeichert.' });
        setEditingItem(null);
      } else {
        const createFns = { property: createProperty, building: createBuilding, unit: createUnit, room: createRoom };
        await createFns[type](data);
        showMessage({ type: 'success', text: 'Objekt erstellt.' });
        setCreatingType(null);
      }
    } catch (err: any) {
      showMessage({ type: 'error', text: `Fehler: ${err.message}` });
    }
  };

  const handleArchive = async (type: AssetType, id: number) => {
    try {
      const archiveFns = { property: archiveProperty, building: archiveBuilding, unit: archiveUnit, room: archiveRoom };
      await archiveFns[type](id);
      showMessage({ type: 'success', text: 'Objekt archiviert.' });
    } catch (err: any) {
      showMessage({ type: 'error', text: `Fehler: ${err.message}` });
    }
  };

  const handleDelete = async (type: AssetType, id: number) => {
    if (!window.confirm('Wirklich löschen?')) return;
    try {
      const deleteFns = { property: deleteProperty, building: deleteBuilding, unit: deleteUnit, room: deleteRoom };
      await deleteFns[type](id);
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
      <InlineListItem
        key={`${type}-${item.id}`}

        isEditing={isEditing}
        isArchived={item.is_archived}
        paddingLeft={paddingLeft}
        
        
        renderDisplay={() => (
          <>
            <div>
              <strong>{title}</strong>
              <span style={{ marginLeft: '1rem', color: '#666', fontSize: '0.9em' }}>{details}</span>
              {item.is_archived && <span className="tag" style={{ marginLeft: '0.5rem' }}>Archiviert</span>}
            </div>
            {!isEditing && renderActions(type, item)}
          </>
        )}
        renderForm={() => (
          <AssetForm 
            type={type} 
            initialData={item} 
            onSave={handleSave} onCancel={() => setEditingItem(null)}
             
              properties={assets?.properties}
            buildings={assets?.buildings}
            units={assets?.units}
            organizationId={1}
          />
        )}
      />
    );
  };

  // Grouping logic for the hierarchical tree
  // Tree: Properties -> Buildings -> Units -> Rooms
  // Also need to show orphaned buildings, units, rooms at the top level
  
  
  const matches = (text: string) => text?.toLowerCase().includes(filterText.toLowerCase());
  
  const filteredProperties = assets?.properties.filter(p => matches(p.name) || matches(p.street) || matches(p.city)) || [];
  const filteredBuildings = assets?.buildings.filter(b => matches(b.name) || matches(b.street) || matches(b.city)) || [];
  const filteredUnits = assets?.units.filter(u => matches(u.label)) || [];
  const filteredRooms = assets?.rooms.filter(r => matches(r.label)) || [];

  const shouldShowProperty = (p: any) => filteredProperties.includes(p) || assets?.buildings.filter(b => b.property_id === p.id).some(shouldShowBuilding);
  const shouldShowBuilding = (b: any) => filteredBuildings.includes(b) || assets?.units.filter(u => u.building_id === b.id).some(shouldShowUnit) || (b.property_id && filteredProperties.find(prop => prop.id === b.property_id));
  const shouldShowUnit = (u: any) => filteredUnits.includes(u) || assets?.rooms.filter(r => r.unit_id === u.id).some(shouldShowRoom) || (u.building_id && filteredBuildings.find(b => b.id === u.building_id));
  const shouldShowRoom = (r: any) => filteredRooms.includes(r) || (r.unit_id && filteredUnits.find(u => u.id === r.unit_id));

  return (
    <div className="asset-registry-view">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
        <h2>Objektverwaltung</h2>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          <input 
            type="text" 
            placeholder="Suchen..." 
            value={filterText} 
            onChange={e => setFilterText(e.target.value)} 
            className="input"
          />
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
      </div>

      {creatingType && (
        <div style={{ marginBottom: '2rem' }}>
          <AssetForm 
            type={creatingType}
            organizationId={1} 
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
        {assets?.properties.filter(shouldShowProperty).map(p => (
          <div key={`p-${p.id}`}>
            {renderItemRow('property', p, p.name, `${p.street}, ${p.city}`)}
            
            {/* Buildings inside property */}
            {assets.buildings.filter(b => b.property_id === p.id && shouldShowBuilding(b)).map(b => (
              <div key={`b-${b.id}`}>
                {renderItemRow('building', b, `Gebäude: ${b.name}`, `${b.street}, ${b.city}`, 2)}
                
                {/* Units inside building */}
                {assets.units.filter(u => u.building_id === b.id && shouldShowUnit(u)).map(u => (
                  <div key={`u-${u.id}`}>
                    {renderItemRow('unit', u, `Wohnung: ${u.label}`, `${u.area_sqm} qm, ${u.room_count} Zimmer`, 4)}
                    
                    {/* Rooms inside unit */}
                    {assets.rooms.filter(r => r.unit_id === u.id && shouldShowRoom(r)).map(r => (
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
        {assets?.buildings.filter(b => !b.property_id && shouldShowBuilding(b)).map(b => (
          <div key={`ob-${b.id}`}>
            {renderItemRow('building', b, `Gebäude: ${b.name}`, `${b.street}, ${b.city}`)}
            
            {assets.units.filter(u => u.building_id === b.id && shouldShowUnit(u)).map(u => (
              <div key={`ou-${u.id}`}>
                {renderItemRow('unit', u, `Wohnung: ${u.label}`, `${u.area_sqm} qm, ${u.room_count} Zimmer`, 2)}
                
                {assets.rooms.filter(r => r.unit_id === u.id && shouldShowRoom(r)).map(r => (
                  <React.Fragment key={`or-${r.id}`}>
                    {renderItemRow('room', r, `Zimmer: ${r.label}`, r.area_sqm ? `${r.area_sqm} qm` : '', 4)}
                  </React.Fragment>
                ))}
              </div>
            ))}
          </div>
        ))}

        {/* Render orphaned Units */}
        {assets?.units.filter(u => !u.building_id && shouldShowUnit(u)).map(u => (
          <div key={`oou-${u.id}`}>
            {renderItemRow('unit', u, `Wohnung: ${u.label}`, `${u.area_sqm} qm, ${u.room_count} Zimmer`)}
            
            {assets.rooms.filter(r => r.unit_id === u.id && shouldShowRoom(r)).map(r => (
              <React.Fragment key={`oor-${r.id}`}>
                {renderItemRow('room', r, `Zimmer: ${r.label}`, r.area_sqm ? `${r.area_sqm} qm` : '', 2)}
              </React.Fragment>
            ))}
          </div>
        ))}

        {/* Render orphaned Rooms (though they require a unit, just in case) */}
        {assets?.rooms.filter(r => !assets.units.find(u => u.id === r.unit_id) && shouldShowRoom(r)).map(r => (
          <React.Fragment key={`ooor-${r.id}`}>
            {renderItemRow('room', r, `Zimmer: ${r.label} (Wohnung nicht gefunden)`, r.area_sqm ? `${r.area_sqm} qm` : '')}
          </React.Fragment>
        ))}
      </div>
    </div>
  );
}
