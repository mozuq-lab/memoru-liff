import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { AuthProvider, CardsProvider, DecksProvider, TutorProvider } from '@/contexts';
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
  TutorPage,
} from '@/pages';

function App() {
  return (
    <Router>
      <AuthProvider>
        <CardsProvider>
          <DecksProvider>
            <TutorProvider>
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
                <Route path="/tutor/:deckId" element={<ProtectedRoute><TutorPage /></ProtectedRoute>} />
              </Routes>
            </Layout>
            </TutorProvider>
          </DecksProvider>
        </CardsProvider>
      </AuthProvider>
    </Router>
  );
}

export default App;
