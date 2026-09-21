export interface Address {
  street: string;
  postal_code: string;
  city: string;
}

interface Props {
  address: Address;
  onChange: (address: Address) => void;
  required?: boolean;
}

export function AddressFields({ address, onChange, required = false }: Props) {
  return (
    <div className="form-group-row" style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
      <div className="form-group" style={{ flex: 1 }}>
        <label>Straße</label>
        <input 
          required={required} 
          type="text" 
          value={address.street} 
          onChange={e => onChange({ ...address, street: e.target.value })} 
          className="input" 
        />
      </div>
      <div className="form-group" style={{ flex: 1 }}>
        <label>PLZ</label>
        <input 
          required={required} 
          type="text" 
          value={address.postal_code} 
          onChange={e => onChange({ ...address, postal_code: e.target.value })} 
          className="input" 
        />
      </div>
      <div className="form-group" style={{ flex: 1 }}>
        <label>Stadt</label>
        <input 
          required={required} 
          type="text" 
          value={address.city} 
          onChange={e => onChange({ ...address, city: e.target.value })} 
          className="input" 
        />
      </div>
    </div>
  );
}
