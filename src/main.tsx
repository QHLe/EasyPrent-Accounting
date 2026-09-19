import React from 'react';
import { createRoot } from 'react-dom/client';

const App = () => (
  <div>
    <h1>EasyPrent Accounting</h1>
    <p>React/Vite setup successful.</p>
  </div>
);

const rootElement = document.getElementById('root');
if (rootElement) {
  const root = createRoot(rootElement);
  root.render(
    <React.StrictMode>
      <App />
    </React.StrictMode>
  );
}

