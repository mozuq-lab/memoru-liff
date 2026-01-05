import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { AuthProvider, CardsProvider } from '@/contexts';
import { Layout, ProtectedRoute } from '@/components/common';
import {
  HomePage,
  GeneratePage,
  CardsPage,
  CardDetailPage,
  SettingsPage,
  LinkLinePage,
  CallbackPage,
} from '@/pages';

function App() {
  return (
    <Router>
      <AuthProvider>
        <CardsProvider>
          <Layout>
            <Routes>
              <Route path="/callback" element={<CallbackPage />} />
              <Route path="/" element={<ProtectedRoute><HomePage /></ProtectedRoute>} />
              <Route path="/generate" element={<ProtectedRoute><GeneratePage /></ProtectedRoute>} />
              <Route path="/cards" element={<ProtectedRoute><CardsPage /></ProtectedRoute>} />
              <Route path="/cards/:id" element={<ProtectedRoute><CardDetailPage /></ProtectedRoute>} />
              <Route path="/settings" element={<ProtectedRoute><SettingsPage /></ProtectedRoute>} />
              <Route path="/link-line" element={<ProtectedRoute><LinkLinePage /></ProtectedRoute>} />
            </Routes>
          </Layout>
        </CardsProvider>
      </AuthProvider>
    </Router>
  );
}

export default App;
