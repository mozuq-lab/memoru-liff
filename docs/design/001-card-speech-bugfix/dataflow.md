# 001-card-speech バグ修正 データフロー図

**作成日**: 2026-03-05
**関連アーキテクチャ**: [architecture.md](architecture.md)
**関連要件定義**: [requirements.md](../../spec/001-card-speech-bugfix/requirements.md)

**【信頼性レベル凡例】**:

- 🔵 **青信号**: 要件定義書・既存実装・契約文書を参考にした確実なフロー
- 🟡 **黄信号**: 要件定義書・既存実装から妥当な推測によるフロー
- 🔴 **赤信号**: 要件定義書・既存実装にない推測によるフロー

---

## REQ-001: 停止トグル — 修正前後のデータフロー 🔵

**信頼性**: 🔵 *spec.md US1 Acceptance Scenario 3・既存実装より*

### 修正前（バグ）

```
ユーザーが SpeechButton（■停止）をタップ
  → FlipCard.speechProps.onSpeakFront()
    → ReviewPage: () => speak(currentCard.front)
      → useSpeech.speak(text):
        1. speechSynthesis.cancel()     ← 一瞬停止
        2. new SpeechSynthesisUtterance  ← 新規発話オブジェクト
        3. speechSynthesis.speak()       ← 再度再生開始 ❌
        4. isSpeaking = true
```

### 修正後

```
ユーザーが SpeechButton（■停止）をタップ
  → FlipCard.speechProps.onSpeakFront()
    → ReviewPage: () => isSpeaking ? cancel() : speak(currentCard.front)
      → [isSpeaking === true の場合]
        → useSpeech.cancel():
          1. speechSynthesis.cancel()   ← 停止 ✅
          2. isSpeaking = false         ← ボタンが ▶ に戻る ✅
      → [isSpeaking === false の場合]
        → useSpeech.speak(text):
          1. speechSynthesis.cancel()   ← 念のため停止
          2. new SpeechSynthesisUtterance
          3. speechSynthesis.speak()    ← 再生開始
          4. isSpeaking = true
```

---

## REQ-002: userId 遅延確定 — 修正前後のデータフロー 🔵

**信頼性**: 🔵 *contracts/hooks.md・既存実装より*

### 修正前（バグ）

```
時刻T0: コンポーネント初回レンダリング
  useAuth() → user = null, userId = undefined
  useSpeechSettings(undefined)
    → useState(() => DEFAULT_SETTINGS)   ← autoPlay=false, rate=1

時刻T1: 認証完了
  useAuth() → user = { sub: "user-123" }, userId = "user-123"
  useSpeechSettings("user-123")
    → useState は再実行されない ❌
    → settings は依然として DEFAULT_SETTINGS ❌
    → localStorage["speech-settings:user-123"] = { autoPlay: true, rate: 1.5 } は無視される
```

### 修正後

```
時刻T0: コンポーネント初回レンダリング
  useAuth() → user = null, userId = undefined
  useSpeechSettings(undefined)
    → useState(() => DEFAULT_SETTINGS)
    → useEffect([undefined]) → userId 無効、スキップ

時刻T1: 認証完了
  useAuth() → user = { sub: "user-123" }, userId = "user-123"
  useSpeechSettings("user-123")
    → useEffect(["user-123"]) → userId 有効 ✅
      → loadSettings("user-123")
        → localStorage.getItem("speech-settings:user-123")
        → parse → { autoPlay: true, rate: 1.5 }
      → setSettings({ autoPlay: true, rate: 1.5 }) ✅
```

---

## REQ-102: localStorage.setItem 例外処理フロー 🟡

**信頼性**: 🟡 *loadSettings 側の try/catch パターンからの妥当な推測*

### 正常時

```
updateSettings({ autoPlay: true })
  → setSettings(prev => { ...prev, autoPlay: true })
  → localStorage.setItem("speech-settings:user-123", '{"autoPlay":true,"rate":1}')
  → state 更新完了 ✅、永続化完了 ✅
```

### Safari Private Mode / 容量超過時

```
updateSettings({ autoPlay: true })
  → setSettings(prev => { ...prev, autoPlay: true })
  → localStorage.setItem(...) → throws QuotaExceededError
  → catch: エラーを無視
  → state 更新完了 ✅、永続化失敗（次回セッションではデフォルトに戻る）
```

---

## 関連文書

- **アーキテクチャ**: [architecture.md](architecture.md)
- **要件定義**: [requirements.md](../../spec/001-card-speech-bugfix/requirements.md)

## 信頼性レベルサマリー

- 🔵 青信号: 3件 (75%)
- 🟡 黄信号: 1件 (25%)
- 🔴 赤信号: 0件 (0%)

**品質評価**: ✅ 高品質
