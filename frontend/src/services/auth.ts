/**
 * 【機能概要】: Keycloak OIDC認証を管理するサービス
 * 【実装方針】: oidc-client-ts の UserManager をラップして認証機能を提供
 * 【テスト対応】: TC-004〜TC-010, TC-017, TC-018
 * 🔵 青信号: 要件定義2.3データフロー・TASK-0012.mdに基づく
 */
import { UserManager, User } from 'oidc-client-ts';
import { oidcConfig } from '@/config/oidc';

/**
 * 【機能概要】: 認証サービスクラス
 * 【実装方針】: シングルトンパターンで UserManager を管理
 * 【テスト対応】: 全認証テストケース
 * 🔵 青信号: TASK-0012.md の実装詳細に基づく
 */
class AuthService {
  // 【プライベートプロパティ】: UserManager インスタンス
  // 🔵 青信号: oidc-client-ts標準の使用方法
  private userManager: UserManager;

  constructor() {
    // 【UserManager初期化】: OIDC設定でUserManagerを作成
    // 🔵 青信号: oidc-client-ts標準の初期化
    this.userManager = new UserManager(oidcConfig);

    // 【イベントリスナー設定】: トークン更新イベントを監視
    // 🔵 青信号: TASK-0012.mdのイベント処理仕様
    this.setupEventListeners();
  }

  /**
   * 【機能概要】: イベントリスナーを設定
   * 【実装方針】: トークン期限切れとログアウトイベントを監視
   * 【テスト対応】: TC-009
   * 🔵 青信号: oidc-client-tsのイベント仕様
   */
  private setupEventListeners(): void {
    // 【トークン期限切れイベント】: 自動リフレッシュをトリガー
    // 🔵 青信号: 要件定義3.1パフォーマンス要件
    this.userManager.events.addAccessTokenExpiring(() => {
      this.refreshToken().catch((error) => {
        console.error('トークンリフレッシュ失敗:', error);
      });
    });

    // 【ログアウトイベント】: セッション終了を検知
    // 🔵 青信号: OIDC標準のセッション管理
    this.userManager.events.addUserSignedOut(() => {
      this.logout().catch((error) => {
        console.error('ログアウト処理失敗:', error);
      });
    });
  }

  /**
   * 【機能概要】: Keycloak認証ページにリダイレクト
   * 【実装方針】: PKCE認証フローを開始
   * 【テスト対応】: TC-004
   * 🔵 青信号: PKCE認証フローの仕様
   */
  async login(): Promise<void> {
    // 【認証開始】: Keycloakへリダイレクト
    // 🔵 青信号: oidc-client-ts標準API
    await this.userManager.signinRedirect();
  }

  /**
   * 【機能概要】: 認証コールバックを処理してトークンを取得
   * 【実装方針】: 認証コードをトークンに交換
   * 【テスト対応】: TC-005, TC-017
   * 🔵 青信号: OIDC標準の認証コールバック
   * @returns {Promise<User>} 認証済みユーザー情報
   */
  async handleCallback(): Promise<User> {
    // 【コールバック処理】: 認証コードからトークンを取得
    // 🔵 青信号: oidc-client-ts標準API
    return await this.userManager.signinRedirectCallback();
  }

  /**
   * 【機能概要】: 保存されたユーザー情報を取得
   * 【実装方針】: localStorageからセッションを復元
   * 【テスト対応】: TC-006
   * 🔵 青信号: セッション管理の仕様
   * @returns {Promise<User | null>} ユーザー情報またはnull
   */
  async getUser(): Promise<User | null> {
    // 【ユーザー取得】: 保存されたセッションからユーザーを取得
    // 🔵 青信号: oidc-client-ts標準API
    return await this.userManager.getUser();
  }

  /**
   * 【機能概要】: アクセストークンを取得
   * 【実装方針】: ユーザー情報からアクセストークンを抽出
   * 【テスト対応】: TC-007
   * 🔵 青信号: JWT形式のトークン
   * @returns {Promise<string | null>} アクセストークンまたはnull
   */
  async getAccessToken(): Promise<string | null> {
    // 【トークン取得】: ユーザーからアクセストークンを抽出
    // 🔵 青信号: oidc-client-ts標準のUserオブジェクト構造
    const user = await this.getUser();
    return user?.access_token ?? null;
  }

  /**
   * 【機能概要】: トークンをリフレッシュ
   * 【実装方針】: サイレントリフレッシュを実行
   * 【テスト対応】: TC-010, TC-018
   * 🔵 青信号: oidc-client-tsのサイレントリフレッシュ仕様
   */
  async refreshToken(): Promise<void> {
    // 【サイレントリフレッシュ】: バックグラウンドでトークンを更新
    // 🔵 青信号: 要件定義3.1パフォーマンス要件
    await this.userManager.signinSilent();
  }

  /**
   * 【機能概要】: ログアウトを実行
   * 【実装方針】: セッションをクリアしてログアウトページにリダイレクト
   * 【テスト対応】: TC-008
   * 🔵 青信号: OIDC標準のログアウト仕様
   */
  async logout(): Promise<void> {
    // 【ログアウト実行】: Keycloakからログアウト
    // 🔵 青信号: oidc-client-ts標準API
    await this.userManager.signoutRedirect();
  }

  /**
   * 【機能概要】: 認証状態を確認
   * 【実装方針】: ユーザーの存在と有効期限を確認
   * 【テスト対応】: isAuthenticated テスト
   * 🔵 青信号: 認証状態確認の仕様
   * @returns {Promise<boolean>} 認証済みの場合はtrue
   */
  async isAuthenticated(): Promise<boolean> {
    // 【認証状態確認】: ユーザーが存在し、トークンが有効かを確認
    // 🔵 青信号: oidc-client-ts標準のexpired判定
    const user = await this.getUser();
    return !!user && !user.expired;
  }
}

// 【シングルトンエクスポート】: アプリケーション全体で共有
// 🔵 青信号: サービスのシングルトンパターン
export const authService = new AuthService();
