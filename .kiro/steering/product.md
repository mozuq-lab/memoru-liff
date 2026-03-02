# Product Overview

Memoru は LINE LIFF (LINE Front-end Framework) を活用した暗記カード（フラッシュカード）アプリケーション。SRS（間隔反復システム）による効率的な学習と、AI によるカード自動生成を組み合わせ、LINE プラットフォーム上でシームレスな学習体験を提供する。

## Core Capabilities

1. **AI カード生成**: Amazon Bedrock (Claude) / Strands Agents SDK を使い、テキスト入力からフラッシュカードを自動生成
2. **SM-2 間隔反復**: SM-2 アルゴリズムに基づく復習スケジューリングで最適な学習タイミングを計算
3. **LINE 統合**: LIFF SDK による LINE 内ブラウザ体験、復習リマインダー通知、LINE アカウント連携
4. **AI 採点・アドバイス**: ユーザー回答の AI 採点、学習傾向に基づく個別アドバイス生成

## Target Use Cases

- LINE ユーザーが日常的にフラッシュカードで学習する
- テキスト（教材・ノートなど）から AI でカードを一括生成し、効率的に暗記する
- SM-2 アルゴリズムに従い、最適なタイミングで LINE 通知を受け取り復習する
- AI が回答を採点し、学習アドバイスを提供することで自律的な学習を支援する

## Value Proposition

- **LINE ネイティブ体験**: 専用アプリのインストール不要、LINE 上で完結する学習フロー
- **AI 活用による学習効率化**: カード生成・採点・アドバイスの自動化で学習の負荷を軽減
- **科学的根拠のある復習**: SM-2 アルゴリズムによるエビデンスベースの間隔反復学習
- **OIDC 認証**: OIDC + PKCE による安全な認証（Keycloak / Cognito 切り替え対応）。ローカル開発ではユーザー名/パスワード認証もサポート

---
_Focus on patterns and purpose, not exhaustive feature lists_
