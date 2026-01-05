/**
 * 【機能概要】: LIFF SDK の初期化と操作を提供するサービス
 * 【実装方針】: LIFF SDKをラップして、アプリケーション固有の機能を提供
 * 【テスト対応】: TC-002, TC-003, TC-013, TC-014
 * 🔵 青信号: 要件定義2.3データフロー・TASK-0012.mdに基づく
 */
import liff from '@line/liff';

// 【定数定義】: LIFF ID を環境変数から取得
// 🔵 青信号: 要件定義の環境変数仕様
const LIFF_ID = import.meta.env.VITE_LIFF_ID || '';

/**
 * 【機能概要】: LIFF SDKを初期化し、必要に応じてログインを実行
 * 【実装方針】: LIFF SDK標準の初期化手順に従う
 * 【テスト対応】: TC-002, TC-003
 * 🔵 青信号: LIFF SDK公式ドキュメントに基づく
 * @throws {Error} LIFF初期化に失敗した場合
 */
export const initializeLiff = async (): Promise<void> => {
  // 【LIFF初期化】: LIFF SDKをLIFF IDで初期化
  // 🔵 青信号: LIFF SDK標準の初期化手順
  await liff.init({ liffId: LIFF_ID });

  // 【ログイン状態確認】: 未ログインの場合はログインを実行
  // 🔵 青信号: 要件定義の認証フロー仕様
  if (!liff.isLoggedIn()) {
    // 【自動ログイン】: LINEログインページにリダイレクト
    liff.login();
  }
};

/**
 * 【機能概要】: LINEユーザーのプロファイル情報を取得
 * 【実装方針】: LIFF SDK の getProfile API を使用
 * 【テスト対応】: getLiffProfile テスト
 * 🔵 青信号: LIFF SDK公式APIに基づく
 * @returns {Promise<Profile>} LINEユーザープロファイル
 */
export const getLiffProfile = async () => {
  // 【プロファイル取得】: LINEユーザー情報を取得
  // 🔵 青信号: LIFF SDK標準API
  return await liff.getProfile();
};

/**
 * 【機能概要】: LIFF ID Tokenを取得
 * 【実装方針】: LIFF SDK の getIDToken API を使用
 * 【テスト対応】: getLiffIdToken テスト
 * 🔵 青信号: LIFF SDK公式APIに基づく
 * @returns {string | null} ID Token または null
 */
export const getLiffIdToken = (): string | null => {
  // 【IDトークン取得】: LINEのID Tokenを取得
  // 🔵 青信号: LIFF SDK標準API
  return liff.getIDToken();
};

/**
 * 【機能概要】: LINE WebView内で実行されているかを判定
 * 【実装方針】: LIFF SDK の isInClient API を使用
 * 【テスト対応】: TC-014
 * 🟡 黄信号: 開発環境での動作考慮
 * @returns {boolean} LINE WebView内の場合はtrue
 */
export const isInLiffClient = (): boolean => {
  // 【環境判定】: LINE WebView内かどうかを判定
  // 🟡 黄信号: 開発環境ではfalseになる可能性
  return liff.isInClient();
};
