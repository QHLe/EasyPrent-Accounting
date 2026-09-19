import React from 'react';

export interface NavigationProps {
  items: { label: string; href: string; isActive?: boolean }[];
}

export const Navigation: React.FC<NavigationProps> = ({ items }) => {
  return (
    <nav className="main-navigation">
      <ul>
        {items.map((item, index) => (
          <li key={index} className={item.isActive ? 'active' : ''}>
            <a href={item.href}>{item.label}</a>
          </li>
        ))}
      </ul>
    </nav>
  );
};

