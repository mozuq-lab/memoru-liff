import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { validateOidcConfig } from './config/oidc'

// 【起動時チェック】: OIDC環境変数のバリデーション
// 🔵 青信号: TASK-0029 C-07 環境変数バリデーション有効化
validateOidcConfig()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
