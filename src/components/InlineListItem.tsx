import type { ReactNode } from 'react';

interface Props {
  isEditing: boolean;
  renderDisplay: () => ReactNode;
  renderForm: () => ReactNode;
  paddingLeft?: number;
  isArchived?: boolean;
}

export function InlineListItem({ 
  isEditing, 
  renderDisplay, 
  renderForm,
  paddingLeft = 0,
  isArchived = false
}: Props) {
  return (
    <div style={{ paddingLeft: `${paddingLeft}rem`, marginBottom: '0.5rem' }}>
      <div 
        style={{ 
          display: 'flex', 
          justifyContent: 'space-between', 
          alignItems: 'center', 
          padding: '0.5rem', 
          backgroundColor: isArchived ? '#f9f9f9' : '#fff', 
          border: '1px solid #eee', 
          borderRadius: '4px' 
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
