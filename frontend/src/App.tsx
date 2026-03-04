import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { AuthProvider, CardsProvider, DecksProvider } from '@/contexts';
import { Layout, ProtectedRoute } from '@/components/common';
import {
  HomePage,
  GeneratePage,
  CardsPage,
  CardDetailPage,
  DecksPage,
  SettingsPage,
  LinkLinePage,
  CallbackPage,
  ReviewPage,
  StatsPage,
} from '@/pages';

function App() {
  return (
    <Router>
      <AuthProvider>
        <CardsProvider>
          <DecksProvider>
            <Layout>
              <Routes>
                <Route path="/callback" element={<CallbackPage />} />
                <Route path="/" element={<ProtectedRoute><HomePage /></ProtectedRoute>} />
                <Route path="/generate" element={<ProtectedRoute><GeneratePage /></ProtectedRoute>} />
                <Route path="/decks" element={<ProtectedRoute><DecksPage /></ProtectedRoute>} />
                <Route path="/cards" element={<ProtectedRoute><CardsPage /></ProtectedRoute>} />
                <Route path="/cards/:id" element={<ProtectedRoute><CardDetailPage /></ProtectedRoute>} />
                <Route path="/settings" element={<ProtectedRoute><SettingsPage /></ProtectedRoute>} />
                <Route path="/review" element={<ProtectedRoute><ReviewPage /></ProtectedRoute>} />
                <Route path="/stats" element={<ProtectedRoute><StatsPage /></ProtectedRoute>} />
                <Route path="/link-line" element={<ProtectedRoute><LinkLinePage /></ProtectedRoute>} />
              </Routes>
            </Layout>
          </DecksProvider>
        </CardsProvider>
      </AuthProvider>
    </Router>
  );
}

export default App;
