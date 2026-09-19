export type MessageType = 'error' | 'success' | 'info';

export interface Message {
  id: string;
  type: MessageType;
  text: string;
}

export interface MessagesProps {
  messages: readonly Message[];
  onDismiss?: (messageId: string) => void;
}

export function Messages({ messages, onDismiss }: MessagesProps) {
  if (messages.length === 0) {
    return null;
  }

  return (
    <div className="messages-container" aria-label="Globale Meldungen">
      {messages.map((message) => (
        <div
          key={message.id}
          className={`message status ${message.type}`}
          role={message.type === 'error' ? 'alert' : 'status'}
        >
          <span>{message.text}</span>
          {onDismiss !== undefined && (
            <button
              type="button"
              onClick={() => onDismiss(message.id)}
              className="close-btn"
              aria-label={`Meldung schließen: ${message.text}`}
            >
              &times;
            </button>
          )}
        </div>
      ))}
    </div>
  );
}
