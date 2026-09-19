import { type MouseEvent } from 'react';

export interface NavigationItem {
  id: string;
  label: string;
  href: string;
  isActive?: boolean;
}

export interface NavigationProps {
  items: readonly NavigationItem[];
  onNavigate?: (itemId: string) => void;
}

export function Navigation({ items, onNavigate }: NavigationProps) {
  const handleClick = (event: MouseEvent<HTMLAnchorElement>, itemId: string) => {
    if (
      onNavigate === undefined ||
      event.defaultPrevented ||
      event.button !== 0 ||
      event.metaKey ||
      event.ctrlKey ||
      event.shiftKey ||
      event.altKey
    ) {
      return;
    }

    event.preventDefault();
    onNavigate(itemId);
  };

  return (
    <nav className="main-navigation" aria-label="Hauptnavigation">
      <ul className="tabs">
        {items.map((item) => (
          <li key={item.id}>
            <a
              href={item.href}
              className={`tab${item.isActive ? ' active' : ''}`}
              aria-current={item.isActive ? 'page' : undefined}
              onClick={(event) => handleClick(event, item.id)}
            >
              {item.label}
            </a>
          </li>
        ))}
      </ul>
    </nav>
  );
}
