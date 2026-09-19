import React, { useState } from 'react';

export interface InlineEditProps {
  value: string;
  onSave: (newValue: string) => Promise<void>;
  type?: 'text' | 'number';
}

export const InlineEdit: React.FC<InlineEditProps> = ({ value, onSave, type = 'text' }) => {
  const [isEditing, setIsEditing] = useState(false);
  const [currentValue, setCurrentValue] = useState(value);
  const [isSaving, setIsSaving] = useState(false);

  React.useEffect(() => {
    setCurrentValue(value);
  }, [value]);

  const handleSave = async () => {
    if (currentValue !== value) {
      setIsSaving(true);
      try {
        await onSave(currentValue);
      } catch (err) {
        // Error handling normally done via context or passed prop
        setCurrentValue(value);
      } finally {
        setIsSaving(false);
      }
    }
    setIsEditing(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      void handleSave();
    } else if (e.key === 'Escape') {
      setCurrentValue(value);
      setIsEditing(false);
    }
  };

  if (isEditing) {
    return (
      <input
        type={type}
        value={currentValue}
        onChange={(e) => setCurrentValue(e.target.value)}
        onBlur={() => void handleSave()}
        onKeyDown={handleKeyDown}
        disabled={isSaving}
        autoFocus
        className="inline-edit-input"
      />
    );
  }

  return (
    <span 
      className="inline-edit-display" 
      onClick={() => setIsEditing(true)}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => { if (e.key === 'Enter') setIsEditing(true); }}
    >
      {value || <span className="empty-placeholder">Click to edit</span>}
    </span>
  );
};

