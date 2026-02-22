# Memoru LIFF Frontend

React + TypeScript + Vite によるフロントエンドアプリケーション。

## セットアップ

```bash
npm install
```

## 開発

```bash
# 開発サーバー起動（ポート3000）
npm run dev

# 型チェック
npm run type-check

# lint
npm run lint
```

## 環境変数

`.env.development` で設定（`.env.example` を参照）:

| 変数名 | 説明 | ローカル開発値 |
|--------|------|---------------|
| `VITE_API_BASE_URL` | バックエンド API URL | `http://localhost:8080` |
| `VITE_LIFF_ID` | LINE LIFF ID（ローカルでは空） | （空） |
| `VITE_KEYCLOAK_URL` | Keycloak URL | `http://localhost:8180` |
| `VITE_KEYCLOAK_REALM` | Keycloak Realm 名 | `memoru` |
| `VITE_KEYCLOAK_CLIENT_ID` | Keycloak クライアント ID | `liff-client` |

## テスト

```bash
# ユニットテスト
npm run test

# カバレッジ付き
npm run test:coverage

# E2E テスト
npm run test:e2e
```

## ビルド

```bash
npm run build
```
