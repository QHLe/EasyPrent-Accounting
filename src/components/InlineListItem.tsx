import type { ReactNode } from 'react';

interface Props {
  isEditing: boolean;
  onEdit: () => void;
  renderDisplay: () => ReactNode;
  renderForm: () => ReactNode;
  paddingLeft?: number;
  isArchived?: boolean;
}

export function InlineListItem({ 
  isEditing, 
  onEdit, 
  renderDisplay, 
  renderForm,
  paddingLeft = 0,
  isArchived = false
}: Props) {
  return (
    <div style={{ paddingLeft: `${paddingLeft}rem`, marginBottom: '0.5rem' }}>
      <div 
        onClick={!isEditing ? onEdit : undefined}
        style={{ 
          display: 'flex', 
          justifyContent: 'space-between', 
          alignItems: 'center', 
          padding: '0.5rem', 
          backgroundColor: isArchived ? '#f9f9f9' : '#fff', 
          border: '1px solid #eee', 
          borderRadius: '4px',
          cursor: !isEditing ? 'pointer' : 'default'
        }}
      >
        {renderDisplay()}
      </div>
      {isEditing && (
        <div style={{ marginTop: '0.5rem' }}>
          {renderForm()}
        </div>
      )}
    </div>
  );
}

