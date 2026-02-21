# TASK-0046 実装ノート: 通知時刻/タイムゾーン判定

**作成日**: 2026-02-21
**対象タスク**: [TASK-0046.md](../../tasks/code-review-fixes-v2/TASK-0046.md)
**TDD段階**: 準備フェーズ

---

## 1. 技術スタック サマリー

### バックエンド

| 項目 | 詳細 |
|------|------|
| **言語・ランタイム** | Python 3.12 |
| **フレームワーク** | AWS Lambda Powertools (v2.x) |
| **フレームワーク** | AWS SAM (Serverless Application Model) |
| **API フレームワーク** | Pydantic v2 (モデル検証) |
| **データベース** | Amazon DynamoDB |
| **タイムゾーン処理** | Python 3.9+ zoneinfo (標準ライブラリ) |
| **依存管理** | pip/requirements.txt |
| **テストフレームワーク** | pytest + pytest-mock |
| **カバレッジ目標** | 80%以上 |

**主要ファイルパス**:
- 通知サービス: `/Volumes/external/dev/memoru-liff/backend/src/services/notification_service.py`
- ユーザーサービス: `/Volumes/external/dev/memoru-liff/backend/src/services/user_service.py`
- ユーザーモデル: `/Volumes/external/dev/memoru-liff/backend/src/models/user.py`
- テスト設定: `/Volumes/external/dev/memoru-liff/backend/tests/conftest.py`
- 既存テスト参照: `/Volumes/external/dev/memoru-liff/backend/tests/unit/test_handler_notification.py`

### フロントエンド

| 項目 | 詳細 |
|------|------|
| **言語・ランタイム** | TypeScript 5.x + React 18 |
| **ビルドツール** | Vite |
| **テストフレームワーク** | Vitest + @testing-library/react |
| **型定義ファイル** | `/Volumes/external/dev/memoru-liff/frontend/src/types/user.ts` |
| **API クライアント** | `/Volumes/external/dev/memoru-liff/frontend/src/services/api.ts` |
| **ページコンポーネント** | `/Volumes/external/dev/memoru-liff/frontend/src/pages/SettingsPage.tsx` |

---

## 2. 既存通知実装パターン

### 2.1 notification_service.py の現状

ファイル: `/Volumes/external/dev/memoru-liff/backend/src/services/notification_service.py`

**現在の process_notifications メソッド**:

```python
def process_notifications(self):
    """Process due notifications for all linked users."""
    current_utc = datetime.now(timezone.utc)
    users = self.user_service.get_linked_users()
    result = ProcessNotificationResult()

    for user in users:
        # 本日既に通知済みをスキップ
        if user.last_notified_date == current_utc.strftime('%Y-%m-%d'):
            result.skipped += 1
            continue

        # 【課題】時刻チェックがない
        # ここに should_notify メソッド追加が必要

        due_count = self.card_service.get_due_card_count(user.user_id)
        if due_count > 0:
            self.send_notification(user, due_count)
            result.sent += 1
        else:
            result.skipped += 1

    return result
```

**問題点**:
- ユーザーのタイムゾーンを考慮していない
- notification_time との一致判定がない
- 任意の時刻に通知が送信される可能性がある

### 2.2 User モデルの現状

ファイル: `/Volumes/external/dev/memoru-liff/backend/src/models/user.py`

```python
class User(BaseModel):
    """User domain model."""
    user_id: str
    line_user_id: Optional[str] = None
    display_name: Optional[str] = None
    picture_url: Optional[str] = None
    settings: dict = Field(default_factory=lambda: {
        "notification_time": "09:00",
        "timezone": "Asia/Tokyo"
    })
    last_notified_date: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None

    def to_response(self) -> UserResponse:
        """Convert to API response model."""
        return UserResponse(
            user_id=self.user_id,
            display_name=self.display_name,
            picture_url=self.picture_url,
            line_linked=self.line_user_id is not None,
            notification_time=self.settings.get("notification_time"),
            timezone=self.settings.get("timezone", "Asia/Tokyo"),
            created_at=self.created_at,
            updated_at=self.updated_at,
        )
```

**現状**:
- settings 辞書に timezone が含まれている（デフォルト: "Asia/Tokyo"）
- notification_time が含まれている（デフォルト: "09:00"）
- 【課題】個別の timezone 属性がない（settings 辞書内に隠れている）

### 2.3 UserService の settings 更新メソッド

ファイル: `/Volumes/external/dev/memoru-liff/backend/src/services/user_service.py`

**現在の update_settings メソッド**:

```python
def update_settings(self, user_id: str, settings: dict) -> User:
    """Update user settings."""
    update_expression_parts = []
    expression_values = {}

    if 'notification_time' in settings:
        update_expression_parts.append('settings.notification_time = :nt')
        expression_values[':nt'] = settings['notification_time']

    # 【課題】timezone パラメータ処理がない

    if update_expression_parts:
        update_expression = "SET " + ", ".join(update_expression_parts)
        self.table.update_item(
            Key={"user_id": user_id},
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_values,
        )

    return self.get_user(user_id)
```

**問題点**:
- timezone パラメータ処理がない
- settings 辞書の更新方式で柔軟性が低い

### 2.4 ハンドラーの settings 更新エンドポイント

ファイル: `/Volumes/external/dev/memoru-liff/backend/src/api/handler.py`

```python
@app.put("/users/me/settings")
@tracer.capture_method
def update_user_settings():
    """Update current user settings."""
    user_id = get_user_id_from_context()

    try:
        body = app.current_event.json_body
        request = UserSettingsRequest(**body)
    except ValidationError as e:
        logger.warning(f"Validation error: {e}")
        return Response(...)

    try:
        user_service.get_or_create_user(user_id)
        user = user_service.update_settings(
            user_id,
            settings={
                'notification_time': request.notification_time,
                # 【課題】timezone が処理されていない
            }
        )
        return {
            "success": True,
            "data": user.to_response().model_dump(mode="json")
        }
    except Exception as e:
        logger.error(f"Error: {e}")
        raise
```

---

## 3. 実装アーキテクチャ

### 3.1 should_notify メソッドの設計

**目的**: ユーザーのローカル時刻が notification_time と一致するかを判定

**入力**:
- user: User オブジェクト（timezone + notification_time を含む）
- current_utc: UTC の datetime オブジェクト

**処理フロー**:

```
1. user.timezone または 'Asia/Tokyo' をデフォルトとする
2. ZoneInfo(tz_name) でユーザーのタイムゾーンを取得
3. current_utc.astimezone(user_tz) でローカル時刻に変換
4. user.notification_time をパース (HH:MM)
5. ローカル時刻 (HH:MM) との差分を計算 (±5分判定)
6. 日付境界をまたぐケース (23:58 と 00:02) を処理
7. 判定結果を返却 (True/False)
```

**実装コード**:

```python
from zoneinfo import ZoneInfo
from datetime import datetime, timezone

def should_notify(self, user, current_utc: datetime) -> bool:
    """ユーザーのローカル時刻が notification_time と一致するか判定"""
    # ステップ1-2: タイムゾーン設定
    tz_name = user.settings.get('timezone', 'Asia/Tokyo')
    user_tz = ZoneInfo(tz_name)

    # ステップ3: ローカル時刻に変換
    local_time = current_utc.astimezone(user_tz)

    # ステップ4: notification_time をパース
    notification_time = user.settings.get('notification_time', '09:00')

    # ステップ5: 分単位での差分を計算
    notif_hour, notif_min = map(int, notification_time.split(':'))
    local_hour, local_min = local_time.hour, local_time.minute

    notif_total_min = notif_hour * 60 + notif_min
    local_total_min = local_hour * 60 + local_min
    diff = abs(local_total_min - notif_total_min)

    # ステップ6: 日付境界をまたぐケース処理
    if diff > 720:  # 12時間以上
        diff = 1440 - diff  # 24時間から引く

    # ステップ7: ±5分の精度で判定
    return diff <= 5
```

**重要な考慮事項**:
- EventBridge の cron 実行間隔（5分）と ±5分判定が対応
- 日付境界ケース（23:58 と 00:02）の処理
- 無効なタイムゾーン名のエラーハンドリング

### 3.2 process_notifications の修正

**修正内容**:

```python
def process_notifications(self):
    """Process due notifications for all linked users."""
    current_utc = datetime.now(timezone.utc)
    users = self.user_service.get_linked_users()
    result = ProcessNotificationResult()

    for user in users:
        # 本日既に通知済みをスキップ
        if user.last_notified_date == current_utc.strftime('%Y-%m-%d'):
            result.skipped += 1
            continue

        # 【追加】ユーザーのローカル時刻が notification_time と一致するか判定
        if not self.should_notify(user, current_utc):
            result.skipped += 1
            continue

        due_count = self.card_service.get_due_card_count(user.user_id)
        if due_count > 0:
            self.send_notification(user, due_count)
            result.sent += 1
        else:
            result.skipped += 1

    return result
```

### 3.3 User モデルの拡張

**目的**: timezone を直接アクセス可能にする

**考慮事項**:
1. DynamoDB はスキーマレスのため DDL 変更不要
2. 既存レコードに timezone がない場合はコード側でデフォルト処理
3. 後方互換性を保つため settings 辞書も保持

**実装方針**:

```python
class User(BaseModel):
    """User domain model."""
    user_id: str
    line_user_id: Optional[str] = None
    display_name: Optional[str] = None
    picture_url: Optional[str] = None
    notification_time: str = '09:00'  # 新規追加（settings から移行）
    timezone: str = 'Asia/Tokyo'      # 新規追加（settings から移行）
    settings: dict = Field(default_factory=lambda: {
        "notification_time": "09:00",
        "timezone": "Asia/Tokyo"
    })
    last_notified_date: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None

    @validator('notification_time')
    def validate_notification_time(cls, v):
        """Validate notification_time format (HH:MM)."""
        if not re.match(r'^\d{2}:\d{2}$', v):
            raise ValueError('notification_time must be in HH:MM format')
        return v

    @validator('timezone')
    def validate_timezone(cls, v):
        """Validate timezone is valid."""
        try:
            ZoneInfo(v)
        except Exception:
            raise ValueError(f'Invalid timezone: {v}')
        return v
```

### 3.4 UserService.update_settings の修正

**修正内容**:

```python
def update_settings(self, user_id: str, settings: dict) -> User:
    """Update user settings."""
    update_expression_parts = []
    expression_values = {}

    if 'notification_time' in settings:
        update_expression_parts.append('notification_time = :nt')
        expression_values[':nt'] = settings['notification_time']
        # 後方互換性: settings 辞書も更新
        update_expression_parts.append('settings.notification_time = :nt')

    if 'timezone' in settings:
        update_expression_parts.append('timezone = :tz')
        expression_values[':tz'] = settings['timezone']
        # 後方互換性: settings 辞書も更新
        update_expression_parts.append('settings.timezone = :tz')

    if update_expression_parts:
        update_expression = "SET " + ", ".join(update_expression_parts)
        self.table.update_item(
            Key={"user_id": user_id},
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_values,
        )

    return self.get_user(user_id)
```

---

## 4. Pydantic リクエスト/レスポンス型

### 4.1 UserSettingsRequest（更新済み）

ファイル: `/Volumes/external/dev/memoru-liff/backend/src/models/user.py`

```python
class UserSettingsRequest(BaseModel):
    """Request model for updating user settings."""
    notification_time: Optional[str] = None
    timezone: Optional[str] = None  # 【新規追加】

    @field_validator('notification_time')
    @classmethod
    def validate_notification_time(cls, v):
        """Validate notification_time format (HH:MM)."""
        if v is None:
            return v
        if not re.match(r'^\d{2}:\d{2}$', v):
            raise ValueError('notification_time must be in HH:MM format')
        return v

    @field_validator('timezone')
    @classmethod
    def validate_timezone(cls, v):
        """Validate timezone is valid."""
        if v is None:
            return v
        try:
            ZoneInfo(v)
        except Exception:
            raise ValueError(f'Invalid timezone: {v}')
        return v
```

### 4.2 UserResponse（既存）

```python
class UserResponse(BaseModel):
    """Response model for user information."""
    user_id: str
    display_name: Optional[str] = None
    picture_url: Optional[str] = None
    line_linked: bool = False
    notification_time: Optional[str] = None
    timezone: str = "Asia/Tokyo"
    created_at: datetime
    updated_at: Optional[datetime] = None
```

---

## 5. フロントエンド実装

### 5.1 UpdateUserRequest 型（更新）

ファイル: `/Volumes/external/dev/memoru-liff/frontend/src/types/user.ts`

```typescript
export interface UpdateUserRequest {
  display_name?: string;
  notification_time?: string;
  timezone?: string;  // 【新規追加】
}
```

### 5.2 SettingsPage コンポーネント

ファイル: `/Volumes/external/dev/memoru-liff/frontend/src/pages/SettingsPage.tsx`

**時刻・タイムゾーン設定フォーム**:

```typescript
const SettingsPage = () => {
  const [notificationTime, setNotificationTime] = useState<string>('09:00');
  const [timezone, setTimezone] = useState<string>('Asia/Tokyo');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const handleSaveSettings = async () => {
    setIsLoading(true);
    setError(null);
    setSuccessMessage(null);

    try {
      await usersApi.updateUser({
        notification_time: notificationTime,
        timezone: timezone,
      });
      setSuccessMessage('設定を更新しました');
    } catch (err) {
      setError('設定の更新に失敗しました');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div>
      <label>
        通知時刻:
        <input
          type="time"
          value={notificationTime}
          onChange={(e) => setNotificationTime(e.target.value)}
        />
      </label>

      <label>
        タイムゾーン:
        <select value={timezone} onChange={(e) => setTimezone(e.target.value)}>
          <option value="Asia/Tokyo">Asia/Tokyo (JST)</option>
          <option value="America/New_York">America/New_York (EST)</option>
          <option value="Europe/London">Europe/London (GMT)</option>
          <option value="UTC">UTC</option>
        </select>
      </label>

      <button onClick={handleSaveSettings} disabled={isLoading}>
        {isLoading ? '保存中...' : '保存'}
      </button>

      {error && <div className="error">{error}</div>}
      {successMessage && <div className="success">{successMessage}</div>}
    </div>
  );
};
```

---

## 6. 単体テスト要件

### 6.1 テストケース1: 通知時刻一致（Asia/Tokyo）

**ファイル**: `backend/tests/unit/test_notification_service.py`

```python
def test_should_notify_matches_notification_time_japan(notification_service):
    """Test should_notify returns True when local time matches notification_time."""
    # Given: timezone='Asia/Tokyo', notification_time='09:00'
    user = User(
        user_id='test-1',
        settings={
            'notification_time': '09:00',
            'timezone': 'Asia/Tokyo'
        }
    )

    # UTC 00:00 = JST 09:00
    current_utc = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    # When
    result = notification_service.should_notify(user, current_utc)

    # Then
    assert result is True
```

### 6.2 テストケース2: 通知時刻不一致

```python
def test_should_notify_no_match_different_time(notification_service):
    """Test should_notify returns False when time doesn't match."""
    # Given: timezone='Asia/Tokyo', notification_time='09:00'
    user = User(
        user_id='test-2',
        settings={
            'notification_time': '09:00',
            'timezone': 'Asia/Tokyo'
        }
    )

    # UTC 06:00 = JST 15:00 (不一致)
    current_utc = datetime(2024, 1, 1, 6, 0, 0, tzinfo=timezone.utc)

    # When
    result = notification_service.should_notify(user, current_utc)

    # Then
    assert result is False
```

### 6.3 テストケース3: ±5分の精度判定

```python
def test_should_notify_within_five_minute_tolerance(notification_service):
    """Test should_notify returns True within ±5 minute window."""
    # Given: timezone='Asia/Tokyo', notification_time='09:00'
    user = User(
        user_id='test-3',
        settings={
            'notification_time': '09:00',
            'timezone': 'Asia/Tokyo'
        }
    )

    # UTC 00:03 = JST 09:03 (3分後、許容範囲内)
    current_utc = datetime(2024, 1, 1, 0, 3, 0, tzinfo=timezone.utc)

    # When
    result = notification_service.should_notify(user, current_utc)

    # Then
    assert result is True
```

### 6.4 テストケース4: ±5分超過

```python
def test_should_notify_outside_tolerance(notification_service):
    """Test should_notify returns False beyond ±5 minute window."""
    # Given: timezone='Asia/Tokyo', notification_time='09:00'
    user = User(
        user_id='test-4',
        settings={
            'notification_time': '09:00',
            'timezone': 'Asia/Tokyo'
        }
    )

    # UTC 00:06 = JST 09:06 (6分後、許容範囲外)
    current_utc = datetime(2024, 1, 1, 0, 6, 0, tzinfo=timezone.utc)

    # When
    result = notification_service.should_notify(user, current_utc)

    # Then
    assert result is False
```

### 6.5 テストケース5: タイムゾーン未設定のデフォルト

```python
def test_should_notify_default_timezone(notification_service):
    """Test should_notify uses Asia/Tokyo as default timezone."""
    # Given: timezone が未設定（settings に timezone がない場合）
    user = User(
        user_id='test-5',
        settings={
            'notification_time': '09:00',
            # timezone は未設定
        }
    )

    # UTC 00:00 = JST 09:00
    current_utc = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    # When
    result = notification_service.should_notify(user, current_utc)

    # Then: Asia/Tokyo として判定されること
    assert result is True
```

### 6.6 テストケース6: 日付境界をまたぐケース

```python
def test_should_notify_date_boundary_case(notification_service):
    """Test should_notify handles date boundary crossing."""
    # Given: timezone='America/New_York', notification_time='23:58'
    user = User(
        user_id='test-6',
        settings={
            'notification_time': '23:58',
            'timezone': 'America/New_York'
        }
    )

    # ローカル時刻が 00:01 の場合
    # 差分は 3分（許容範囲内）
    current_utc = datetime(2024, 1, 1, 5, 1, 0, tzinfo=timezone.utc)  # EST 00:01

    # When
    result = notification_service.should_notify(user, current_utc)

    # Then
    assert result is True
```

### 6.7 テストケース7: 異なるタイムゾーンでの通知判定

```python
def test_should_notify_different_timezone(notification_service):
    """Test should_notify with different timezone (America/New_York)."""
    # Given: timezone='America/New_York' (UTC-5), notification_time='09:00'
    user = User(
        user_id='test-7',
        settings={
            'notification_time': '09:00',
            'timezone': 'America/New_York'
        }
    )

    # UTC 14:00 = EST 09:00
    current_utc = datetime(2024, 1, 1, 14, 0, 0, tzinfo=timezone.utc)

    # When
    result = notification_service.should_notify(user, current_utc)

    # Then
    assert result is True
```

### 6.8 テストケース8: process_notifications での should_notify 使用

```python
def test_process_notifications_uses_should_notify(notification_service, user_service):
    """Test process_notifications uses should_notify to filter users."""
    # Given: 通知時刻と一致するユーザーと不一致のユーザー
    user1 = user_service.create_user('user-1')
    user_service.update_settings('user-1', {
        'notification_time': '09:00',
        'timezone': 'Asia/Tokyo'
    })

    user2 = user_service.create_user('user-2')
    user_service.update_settings('user-2', {
        'notification_time': '15:00',
        'timezone': 'Asia/Tokyo'
    })

    # When: UTC 00:00 (JST 09:00) に process_notifications を実行
    current_utc = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    with patch('datetime.now', return_value=current_utc):
        result = notification_service.process_notifications()

    # Then: user1 のみ通知が送信され、user2 はスキップされること
    assert result.sent == 1  # user1 のみ
    assert result.skipped == 1  # user2 はスキップ
```

### 6.9 テストケース9: 無効なタイムゾーン名のエラーハンドリング

```python
def test_should_notify_invalid_timezone_handling(notification_service):
    """Test should_notify handles invalid timezone gracefully."""
    # Given: 無効なタイムゾーン名
    user = User(
        user_id='test-9',
        settings={
            'notification_time': '09:00',
            'timezone': 'Invalid/Timezone'
        }
    )

    current_utc = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    # When/Then: エラーが発生しないか、デフォルトとして処理されること
    try:
        result = notification_service.should_notify(user, current_utc)
        # デフォルトタイムゾーンで処理される場合
        assert result is not None
    except ValueError:
        # エラーが発生する場合
        pass
```

---

## 7. 統合テスト要件

### 7.1 統合テスト1: タイムゾーン対応通知フロー

**テスト内容**: EventBridge → Lambda → should_notify判定 → 条件付き通知送信

```python
def test_integration_timezone_aware_notification_flow(dynamodb_resource, user_service, notification_service):
    """Test end-to-end notification flow with timezone awareness."""
    # Given: 複数ユーザーの異なるタイムゾーン設定
    user_japan = user_service.create_user('user-japan')
    user_service.update_settings('user-japan', {
        'notification_time': '09:00',
        'timezone': 'Asia/Tokyo'
    })

    user_newyork = user_service.create_user('user-newyork')
    user_service.update_settings('user-newyork', {
        'notification_time': '09:00',
        'timezone': 'America/New_York'
    })

    # When: UTC 00:00 (JST 09:00, EST 19:00の前日) に通知処理を実行
    current_utc = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    with patch('notification_service.datetime') as mock_datetime:
        mock_datetime.now.return_value = current_utc
        result = notification_service.process_notifications()

    # Then: 日本のユーザーのみ通知が送信される
    assert result.sent == 1  # user-japan のみ
    assert result.skipped >= 1  # user-newyork はスキップ
```

---

## 8. 実装手順（フェーズ別）

### 8.1 RED フェーズ（テスト記述）

1. テストケース 1-9 を実装
2. `pytest tests/unit/test_notification_service.py -v` ですべて失敗することを確認

### 8.2 GREEN フェーズ（最小実装）

#### 実装ステップ 1: should_notify メソッド追加

**ファイル**: `/Volumes/external/dev/memoru-liff/backend/src/services/notification_service.py`

```python
from zoneinfo import ZoneInfo

def should_notify(self, user, current_utc: datetime) -> bool:
    """ユーザーのローカル時刻が notification_time と一致するか判定"""
    tz_name = user.settings.get('timezone', 'Asia/Tokyo')

    try:
        user_tz = ZoneInfo(tz_name)
    except Exception:
        # 無効なタイムゾーンの場合はデフォルトを使用
        user_tz = ZoneInfo('Asia/Tokyo')

    local_time = current_utc.astimezone(user_tz)
    notification_time = user.settings.get('notification_time', '09:00')

    notif_hour, notif_min = map(int, notification_time.split(':'))
    local_hour, local_min = local_time.hour, local_time.minute

    notif_total_min = notif_hour * 60 + notif_min
    local_total_min = local_hour * 60 + local_min
    diff = abs(local_total_min - notif_total_min)

    if diff > 720:
        diff = 1440 - diff

    return diff <= 5
```

#### 実装ステップ 2: process_notifications で should_notify を使用

**ファイル**: `/Volumes/external/dev/memoru-liff/backend/src/services/notification_service.py`

```python
def process_notifications(self):
    """Process due notifications for all linked users."""
    current_utc = datetime.now(timezone.utc)
    users = self.user_service.get_linked_users()
    result = ProcessNotificationResult()

    for user in users:
        if user.last_notified_date == current_utc.strftime('%Y-%m-%d'):
            result.skipped += 1
            continue

        # 【追加】
        if not self.should_notify(user, current_utc):
            result.skipped += 1
            continue

        due_count = self.card_service.get_due_card_count(user.user_id)
        if due_count > 0:
            self.send_notification(user, due_count)
            result.sent += 1
        else:
            result.skipped += 1

    return result
```

#### 実装ステップ 3: UserService.update_settings に timezone 処理追加

**ファイル**: `/Volumes/external/dev/memoru-liff/backend/src/services/user_service.py`

```python
def update_settings(self, user_id: str, settings: dict) -> User:
    """Update user settings."""
    update_expression_parts = []
    expression_values = {}

    if 'notification_time' in settings:
        update_expression_parts.append('settings.notification_time = :nt')
        expression_values[':nt'] = settings['notification_time']

    if 'timezone' in settings:
        update_expression_parts.append('settings.timezone = :tz')
        expression_values[':tz'] = settings['timezone']

    if update_expression_parts:
        update_expression = "SET " + ", ".join(update_expression_parts)
        self.table.update_item(
            Key={"user_id": user_id},
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_values,
        )

    return self.get_user(user_id)
```

#### 実装ステップ 4: ハンドラーで timezone パラメータ処理

**ファイル**: `/Volumes/external/dev/memoru-liff/backend/src/api/handler.py`

```python
@app.put("/users/me/settings")
@tracer.capture_method
def update_user_settings():
    """Update current user settings."""
    user_id = get_user_id_from_context()

    try:
        body = app.current_event.json_body
        request = UserSettingsRequest(**body)
    except ValidationError as e:
        logger.warning(f"Validation error: {e}")
        return Response(...)

    try:
        user_service.get_or_create_user(user_id)
        settings_to_update = {}

        if request.notification_time:
            settings_to_update['notification_time'] = request.notification_time
        if request.timezone:
            settings_to_update['timezone'] = request.timezone

        user = user_service.update_settings(user_id, settings_to_update)
        return {
            "success": True,
            "data": user.to_response().model_dump(mode="json")
        }
    except Exception as e:
        logger.error(f"Error: {e}")
        raise
```

#### 実装ステップ 5: フロントエンド型定義更新

**ファイル**: `/Volumes/external/dev/memoru-liff/frontend/src/types/user.ts`

```typescript
export interface UpdateUserRequest {
  display_name?: string;
  notification_time?: string;
  timezone?: string;  // 【新規追加】
}
```

### 8.3 REFACTOR フェーズ（リファクタリング）

- エラーハンドリングの統一性確認
- should_notify メソッドの例外処理の堅牢性確認
- テストカバレッジ 80%以上確認
- zoneinfo の使用が適切か確認
- User モデルの settings 辞書との関係性を確認

---

## 9. 関連ファイル一覧

| ファイル | 役割 | 修正範囲 |
|---------|------|---------|
| `/Volumes/external/dev/memoru-liff/backend/src/services/notification_service.py` | 通知サービス | should_notify メソッド追加、process_notifications 修正 |
| `/Volumes/external/dev/memoru-liff/backend/src/services/user_service.py` | ユーザーサービス | update_settings に timezone 処理追加 |
| `/Volumes/external/dev/memoru-liff/backend/src/models/user.py` | Pydantic モデル | User モデルと UserSettingsRequest の timezone フィールド |
| `/Volumes/external/dev/memoru-liff/backend/src/api/handler.py` | ハンドラー | update_user_settings で timezone パラメータ処理 |
| `/Volumes/external/dev/memoru-liff/frontend/src/types/user.ts` | TypeScript 型定義 | UpdateUserRequest に timezone フィールド |
| `/Volumes/external/dev/memoru-liff/backend/tests/unit/test_notification_service.py` | テスト | should_notify テストケース |

---

## 10. 信頼性レベル別実装チェックリスト

### 🔵 青信号（確実な定義）

- [x] should_notify メソッドがタイムゾーン変換を行う
- [x] ±5分精度で time matching を実装
- [x] process_notifications で should_notify を使用
- [x] user.settings に timezone フィールドが存在
- [x] update_settings で timezone パラメータを処理
- [x] ZoneInfo を使用してタイムゾーン処理

### 🟡 黄信号（要件定義書から妥当な推測）

- [ ] デフォルトタイムゾーン: Asia/Tokyo
- [ ] EventBridge 実行間隔（5分）と判定精度の対応
- [ ] 日付境界ケースの処理方法

### 🔴 赤信号（確実でない推測）

- 特に該当なし

---

## 11. テスト実行コマンド参考

### バックエンド

```bash
cd /Volumes/external/dev/memoru-liff/backend

# すべてのテストを実行
make test

# 特定のテストファイルを実行
pytest tests/unit/test_notification_service.py -v

# カバレッジレポート付きで実行
pytest --cov=src --cov-report=html tests/

# 特定のテストケースのみ実行
pytest tests/unit/test_notification_service.py::test_should_notify_matches_notification_time_japan -v
```

### フロントエンド

```bash
cd /Volumes/external/dev/memoru-liff/frontend

# すべてのテストを実行
npm run test

# 特定のテストファイルを実行
npm run test -- SettingsPage.test.tsx

# カバレッジレポート付きで実行
npm run test -- --coverage
```

---

## 12. 次のステップ

1. **RED フェーズ**: テストケース 1-9 を実装し、すべてが失敗することを確認
2. **GREEN フェーズ**: 実装ステップ 1-5 を順序通りに実装し、すべてのテストが成功することを確認
3. **REFACTOR フェーズ**: コード品質の改善と統一性確認
4. **検証**: TASK-0046.md の完了条件をチェック
5. **コミット**: `TASK-0046: 通知時刻/タイムゾーン判定`

---

## 13. 予想される課題とその対策

### 課題 1: 無効なタイムゾーン名の処理

**現象**: ZoneInfo() でエラーが発生

**対策**: try-except でラップし、Asia/Tokyo をデフォルトとして使用

### 課題 2: 夏時間（DST）の考慮

**現象**: DST 期間中に時刻がズレる可能性

**対策**: ZoneInfo が自動的に DST を処理するため、追加対応不要

### 課題 3: テストで現在時刻をモック

**現象**: テストで特定の UTC 時刻を固定したい

**対策**: `unittest.mock.patch('datetime.now')` を使用

### 課題 4: DynamoDB での settings 辞書の互換性

**現象**: 既存レコードに timezone がない

**対策**: コード側で `.get('timezone', 'Asia/Tokyo')` でデフォルト処理

---

**作成者**: Claude Code
**最終更新**: 2026-02-21
