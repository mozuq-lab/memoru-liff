/**
 * 【型定義】: 認証ユーザー情報
 * oidc-client-ts の User 型から必要な情報のみを抽出した共有型。
 * useAuth と AuthContext で一本化するため types に集約する。
 */
export interface AuthUser {
  access_token: string;
  expired: boolean;
  profile?: {
    sub: string;
    email?: string;
    name?: string;
  };
}
