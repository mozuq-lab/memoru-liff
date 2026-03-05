# memoru-liff-copilot Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-03-04

## Active Technologies

- TypeScript 5.x, React 18 + Tailwind CSS（既存）, Vitest + React Testing Library（テスト）、新規ライブラリ追加なし (001-card-search)
- Web Speech API（ブラウザ組み込み）, localStorage 設定永続化 (001-card-speech)

## Project Structure

```text
backend/
frontend/
tests/
```

## Commands

npm test && npm run lint

## Code Style

TypeScript 5.x, React 18: Follow standard conventions

## Recent Changes

- 001-card-search: Added TypeScript 5.x, React 18 + Tailwind CSS（既存）, Vitest + React Testing Library（テスト）、新規ライブラリ追加なし
- 001-card-speech: Added Web Speech API integration (useSpeech hook, useSpeechSettings hook, SpeechButton component). FlipCard extended with optional speechProps. SettingsPage extended with speech settings section. No new npm packages.

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
