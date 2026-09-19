import React from 'react';

export interface MessageProps {
  type: 'error' | 'success' | 'info';
  text: string;
  onDismiss?: () => void;
}

export const Messages: React.FC<{ messages: MessageProps[] }> = ({ messages }) => {
  if (messages.length === 0) return null;

  return (
    <div className="messages-container">
      {messages.map((msg, idx) => (
        <div key={idx} className={`message message-${msg.type}`}>
          <span>{msg.text}</span>
          {msg.onDismiss && (
            <button onClick={msg.onDismiss} className="close-btn" aria-label="Dismiss message">
              &times;
            </button>
          )}
        </div>
      ))}
    </div>
  );
};

