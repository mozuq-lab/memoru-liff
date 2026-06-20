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
   * 【実装方針】: ログアウトイベントとサイレントリニューエラーを監視
   * 【テスト対応】: TC-009
   * 🔵 青信号: oidc-client-tsのイベント仕様
   *
   * 注 (A-2): トークン更新の起点は automaticSilentRenew (ライブラリ内蔵の
   * expiring → signinSilent) と API 401 リトライの 2 経路に集約する。
   * 以前ここにあった addAccessTokenExpiring の手動 refresh は
   * automaticSilentRenew と二重更新になるため削除した。
   */
  private setupEventListeners(): void {
    // 【ログアウトイベント】: セッション終了を検知
    // 🔵 青信号: OIDC標準のセッション管理
    this.userManager.events.addUserSignedOut(() => {
      this.logout().catch((error) => {
        console.error('ログアウト処理失敗:', error);
      });
    });

    // 【サイレントリニュー失敗】: 自動更新失敗を記録（401 リトライ経路が残るため致命ではない）
    this.userManager.events.addSilentRenewError((error) => {
      console.error('サイレントリニュー失敗:', error);
    });
  }

  /**
   * 【機能概要】: 認証ユーザーの変化を購読する (A-3)
   * 【実装方針】: userLoaded / userUnloaded / accessTokenExpired を監視し、
   * トークン更新・失効・ログアウトを呼び出し元（useAuth）へ通知する
   * @param callback - ユーザー変化時に最新の User（失効/ログアウト時は null）で呼ばれる
   * @returns 購読解除関数
   */
  onUserChanged(callback: (user: User | null) => void): () => void {
    const onLoaded = (user: User) => callback(user);
    const onUnloaded = () => callback(null);
    // accessTokenExpired 時は expired=true の User を通知して
    // isAuthenticated=false へ遷移させる（自動更新失敗後の最終状態）
    const onExpired = () =>
      this.getUser()
        .then(callback)
        .catch(() => callback(null));

    this.userManager.events.addUserLoaded(onLoaded);
    this.userManager.events.addUserUnloaded(onUnloaded);
    this.userManager.events.addAccessTokenExpired(onExpired);

    return () => {
      this.userManager.events.removeUserLoaded(onLoaded);
      this.userManager.events.removeUserUnloaded(onUnloaded);
      this.userManager.events.removeAccessTokenExpired(onExpired);
    };
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
   * 【機能概要】: サイレントリニュー用 iframe のコールバックを処理する (S-2)
   * 【実装方針】: /silent-renew ルートから呼び出され、親ウィンドウの
   * UserManager へ認証応答を引き渡す
   */
  async handleSilentCallback(): Promise<void> {
    await this.userManager.signinSilentCallback();
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
    //
    // 注 (L-23): ここで error を再 throw する設計は意図的。呼び出し元
    // useAuth.logout は try/catch/finally 構造になっており、
    //   - catch で setError によりログアウト失敗をユーザーへ通知し、
    //   - finally で setIsLoading(false) を必ず実行する
    // ため、本メソッドが throw しても isLoading が残留することはない。
    // 将来この throw を安易に握りつぶすと、呼び出し元が失敗を検知できなくなる
    // 点に注意（成功時はブラウザが IdP へ遷移しコンポーネントがアンマウント
    // されるが、開発環境等で signoutRedirect が遷移せず resolve した場合は
    // removeUser → userUnloaded 経由で状態がクリアされる）。
    try {
      await this.userManager.signoutRedirect();
    } catch (error) {
      // 【ローカルクリーンアップ】(A-1): リダイレクトに失敗しても
      // ローカルのトークンは必ず破棄する（userUnloaded イベントが発火し
      // useAuth / apiClient の状態もクリアされる）
      await this.userManager.removeUser();
      throw error;
    }
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
