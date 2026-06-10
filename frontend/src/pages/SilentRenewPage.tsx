import { useEffect, useRef } from 'react';
import { authService } from '@/services/auth';

/**
 * 【機能概要】: サイレントリニュー用 iframe のコールバックページ (S-2)
 * 【実装方針】: oidc-client-ts の silent_redirect_uri (/silent-renew) から
 * 読み込まれ、signinSilentCallback() で親ウィンドウの UserManager に
 * 認証応答を引き渡す。iframe 内で不可視に動作するため UI は描画しない。
 */
export const SilentRenewPage = () => {
  // StrictMode の effect 二重実行で signinSilentCallback が
  // 二重に走らないよう ref でガードする
  const processedRef = useRef(false);

  useEffect(() => {
    if (processedRef.current) return;
    processedRef.current = true;

    authService.handleSilentCallback().catch((err) => {
      // 失敗してもユーザー操作は不要（automaticSilentRenew のリトライと
      // API 401 リトライ経路でリカバリされる）
      console.error('Silent renew callback error:', err);
    });
  }, []);

  return null;
};
