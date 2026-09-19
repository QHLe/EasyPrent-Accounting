import {
  createContext,
  Fragment,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';

import { Messages, type MessageType } from '../components/Messages';
import { Navigation } from '../components/Navigation';

export type ShellSection = Readonly<{
  id: string;
  label: string;
  content: ReactNode;
}>;

export type GlobalMessageInput = Readonly<{
  type: MessageType;
  text: string;
}>;

interface GlobalMessageActions {
  showMessage: (message: GlobalMessageInput) => void;
}

export interface AppShellProps {
  sections: readonly ShellSection[];
  initialSectionId?: string;
}

const GlobalMessagesContext = createContext<GlobalMessageActions | null>(null);

export function useGlobalMessages(): GlobalMessageActions {
  const actions = useContext(GlobalMessagesContext);
  if (actions === null) {
    throw new Error('useGlobalMessages must be used within AppShell.');
  }
  return actions;
}

function readSectionIdFromHash(): string {
  const encodedSectionId = window.location.hash.slice(1);
  try {
    return decodeURIComponent(encodedSectionId);
  } catch {
    return '';
  }
}

export function AppShell({ sections, initialSectionId }: AppShellProps) {
  if (sections.length === 0) {
    throw new Error('AppShell requires at least one section.');
  }

  const fallbackSection =
    sections.find((section) => section.id === initialSectionId) ?? sections[0];
  const resolveSectionId = useCallback(
    (candidate: string) =>
      sections.some((section) => section.id === candidate)
        ? candidate
        : fallbackSection.id,
    [fallbackSection.id, sections],
  );
  const [activeSectionId, setActiveSectionId] = useState(() =>
    resolveSectionId(readSectionIdFromHash()),
  );
  const [messages, setMessages] = useState<
    Array<GlobalMessageInput & Readonly<{ id: string }>>
  >([]);
  const nextMessageId = useRef(0);

  useEffect(() => {
    const selectLocationSection = () => {
      setActiveSectionId(resolveSectionId(readSectionIdFromHash()));
    };

    window.addEventListener('hashchange', selectLocationSection);
    window.addEventListener('popstate', selectLocationSection);
    return () => {
      window.removeEventListener('hashchange', selectLocationSection);
      window.removeEventListener('popstate', selectLocationSection);
    };
  }, [resolveSectionId]);

  const showMessage = useCallback((message: GlobalMessageInput) => {
    nextMessageId.current += 1;
    const id = `global-message-${nextMessageId.current}`;
    setMessages((current) => [...current, { ...message, id }]);
  }, []);

  const dismissMessage = useCallback((messageId: string) => {
    setMessages((current) => current.filter((message) => message.id !== messageId));
  }, []);

  const messageActions = useMemo(() => ({ showMessage }), [showMessage]);
  const activeSection =
    sections.find((section) => section.id === activeSectionId) ?? fallbackSection;
  const navigationItems = sections.map((section) => ({
    id: section.id,
    label: section.label,
    href: `#${encodeURIComponent(section.id)}`,
    isActive: section.id === activeSection.id,
  }));

  const navigate = (sectionId: string) => {
    const resolvedSectionId = resolveSectionId(sectionId);
    setActiveSectionId(resolvedSectionId);
    const nextHash = `#${encodeURIComponent(resolvedSectionId)}`;
    if (window.location.hash !== nextHash) {
      window.history.pushState(null, '', nextHash);
    }
  };

  return (
    <GlobalMessagesContext.Provider value={messageActions}>
      <div className="app">
        <div className="shell-links">
          <a href="/openapi.json">OpenAPI JSON</a>
        </div>
        <header className="hero">
          <h1>EasyPrent Accounting</h1>
          <p className="lede">
            Immobilien, Mietverhältnisse, Kosten und Abrechnungen an einem Ort verwalten.
          </p>
        </header>
        <main className="main-grid">
          <Navigation items={navigationItems} onNavigate={navigate} />
          <p className="visually-hidden route-status" role="status" aria-atomic="true">
            Aktiver Bereich: {activeSection.label}
          </p>
          <Messages messages={messages} onDismiss={dismissMessage} />
          <div className="shell-content">
            <Fragment key={activeSection.id}>{activeSection.content}</Fragment>
          </div>
        </main>
      </div>
    </GlobalMessagesContext.Provider>
  );
}
