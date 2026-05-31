import React from 'react';
import ReactDOM from 'react-dom/client';
import * as Sentry from "@sentry/react";
import { ClerkProvider } from '@clerk/clerk-react';
import { BrowserRouter } from 'react-router-dom';
import './index.css';
import App from './App';

const CLERK_PUBLISHABLE_KEY = process.env.REACT_APP_CLERK_PUBLISHABLE_KEY;

if (!CLERK_PUBLISHABLE_KEY) {
  console.error('⚠️ REACT_APP_CLERK_PUBLISHABLE_KEY is missing. Add it to frontend/.env');
}

// Khởi tạo Sentry (phải gọi trước mọi thứ khác)
if (process.env.REACT_APP_SENTRY_DSN) {
  Sentry.init({
    dsn: process.env.REACT_APP_SENTRY_DSN,
    integrations: [
      Sentry.browserTracingIntegration(),
      Sentry.replayIntegration({ maskAllText: true, blockAllMedia: true }),
    ],
    tracesSampleRate: 0.3,
    replaysSessionSampleRate: 0,    // Không record phiên thông thường
    replaysOnErrorSampleRate: 0.5,  // Record 50% phiên có lỗi (rất hữu ích để debug)
    environment: "production",
    beforeSend(event) {
      // Lọc bỏ dữ liệu y tế nhạy cảm khỏi breadcrumbs
      if (event.breadcrumbs) {
        event.breadcrumbs = event.breadcrumbs.map(crumb => {
          if (crumb.data) {
            const sensitiveKeys = ['content', 'query', 'message', 'health_profile',
              'chronic_diseases', 'allergies', 'current_medications'];
            sensitiveKeys.forEach(key => {
              if (crumb.data[key]) crumb.data[key] = '[REDACTED]';
            });
          }
          return crumb;
        });
      }
      return event;
    },
  });
}

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <Sentry.ErrorBoundary fallback={<p style={{ padding: '20px', textAlign: 'center', color: '#e53e3e' }}>Đã xảy ra lỗi hệ thống. Vui lòng tải lại trang.</p>}>
      <ClerkProvider publishableKey={CLERK_PUBLISHABLE_KEY || ''}>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </ClerkProvider>
    </Sentry.ErrorBoundary>
  </React.StrictMode>
);

