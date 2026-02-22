/**
 * 【機能概要】: Keycloak OIDC設定を環境変数から生成する
 * 【実装方針】: oidc-client-ts の UserManagerSettings 形式で設定を提供
 * 【テスト対応】: TC-001, TC-023, TC-024
 * 🔵 青信号: 要件定義2.1入力パラメータに基づく
 */
import type { UserManagerSettings } from 'oidc-client-ts';

// 【定数定義】: 環境変数から取得する設定値
// 🔵 青信号: 要件定義の環境変数仕様に基づく
const KEYCLOAK_URL = import.meta.env.VITE_KEYCLOAK_URL || '';
const KEYCLOAK_REALM = import.meta.env.VITE_KEYCLOAK_REALM || '';
const KEYCLOAK_CLIENT_ID = import.meta.env.VITE_KEYCLOAK_CLIENT_ID || '';

/**
 * 【機能概要】: OIDC設定のバリデーションを行う
 * 【実装方針】: 必須環境変数の存在確認とエラー通知
 * 【テスト対応】: TC-023, TC-024
 * 🟡 黄信号: 要件定義から推測したバリデーション要件
 */
export const validateOidcConfig = (): void => {
  // 【入力値検証】: 必須環境変数の存在確認
  // 🟡 黄信号: 入力バリデーションのベストプラクティス
  const requiredVars = [
    { name: 'VITE_KEYCLOAK_URL', value: KEYCLOAK_URL },
    { name: 'VITE_KEYCLOAK_REALM', value: KEYCLOAK_REALM },
    { name: 'VITE_KEYCLOAK_CLIENT_ID', value: KEYCLOAK_CLIENT_ID },
  ];

  for (const { name, value } of requiredVars) {
    if (!value || value.trim() === '') {
      // 【エラー処理】: 未設定または空文字列の場合はエラーをスロー
      throw new Error(`環境変数 ${name} が設定されていません`);
    }
  }
};

/**
 * 【機能概要】: Keycloak OIDC接続設定オブジェクト
 * 【実装方針】: PKCE認証フローに必要なパラメータを設定
 * 【テスト対応】: TC-001
 * 🔵 青信号: 要件定義2.1、OIDC標準仕様に基づく
 */
export const oidcConfig: UserManagerSettings = {
  // 【authority設定】: Keycloak Realm のOIDCエンドポイント
  // 🔵 青信号: Keycloak標準のURL形式
  authority: `${KEYCLOAK_URL}/realms/${KEYCLOAK_REALM}`,

  // 【client_id設定】: Keycloak で登録したクライアントID
  // 🔵 青信号: 要件定義の入力パラメータ
  client_id: KEYCLOAK_CLIENT_ID,

  // 【redirect_uri設定】: 認証後のコールバックURL
  // 🔵 青信号: OIDC標準の認証フロー
  redirect_uri: `${window.location.origin}/callback`,

  // 【post_logout_redirect_uri設定】: ログアウト後のリダイレクトURL
  // 🔵 青信号: OIDC標準のログアウトフロー
  post_logout_redirect_uri: window.location.origin,

  // 【response_type設定】: Authorization Code フロー
  // 🔵 青信号: PKCE認証フローの仕様
  response_type: 'code',

  // 【scope設定】: OpenID Connect 標準スコープ
  // 🔵 青信号: OIDC標準スコープ
  scope: 'openid profile email',

  // 【automaticSilentRenew設定】: トークンの自動リフレッシュ
  // 🔵 青信号: 要件定義3.1パフォーマンス要件
  automaticSilentRenew: true,

  // 【silent_redirect_uri設定】: サイレントリフレッシュ用URL
  // 🔵 青信号: oidc-client-ts標準設定
  silent_redirect_uri: `${window.location.origin}/silent-renew`,
};
