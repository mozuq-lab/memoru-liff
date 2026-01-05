/**
 * 【機能概要】: 設定画面
 * 【実装方針】: 通知時間設定、アカウント情報、ログアウト機能を提供
 * 【テスト対応】: TASK-0018 テストケース1〜7
 * 🔵 青信号: user-stories.md 4.2より
 */
import { useState, useEffect, useCallback } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Navigation } from '@/components/Navigation';
import { Loading } from '@/components/common/Loading';
import { Error } from '@/components/common/Error';
import { usersApi } from '@/services/api';
import { useAuth } from '@/hooks/useAuth';
import type { User } from '@/types';

const NOTIFICATION_TIMES = [
  { value: '07:00', label: '07:00' },
  { value: '09:00', label: '09:00' },
  { value: '12:00', label: '12:00' },
  { value: '18:00', label: '18:00' },
  { value: '21:00', label: '21:00' },
];

/**
 * 【機能概要】: 設定ページコンポーネント
 */
export const SettingsPage = () => {
  const navigate = useNavigate();
  const { logout } = useAuth();
  const [user, setUser] = useState<User | null>(null);
  const [selectedTime, setSelectedTime] = useState<string>('09:00');
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // 【ユーザー情報取得】
  const fetchUser = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const data = await usersApi.getCurrentUser();
      setUser(data);
      setSelectedTime(data.notification_time || '09:00');
    } catch (err) {
      setError('設定の取得に失敗しました');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchUser();
  }, [fetchUser]);

  // 【成功メッセージの自動非表示】
  useEffect(() => {
    if (successMessage) {
      const timer = setTimeout(() => setSuccessMessage(null), 3000);
      return () => clearTimeout(timer);
    }
  }, [successMessage]);

  // 【保存ハンドラ】
  const handleSave = async () => {
    setIsSaving(true);
    setError(null);

    try {
      const updatedUser = await usersApi.updateUser({ notification_time: selectedTime });
      setUser(updatedUser);
      setSuccessMessage('設定を保存しました');
    } catch (err) {
      setError('設定の保存に失敗しました');
    } finally {
      setIsSaving(false);
    }
  };

  // 【ログアウトハンドラ】
  const handleLogout = async () => {
    setIsLoggingOut(true);
    setError(null);

    try {
      await logout();
      navigate('/');
    } catch (err) {
      setError('ログアウトに失敗しました');
      setIsLoggingOut(false);
    }
  };

  const hasChanges = user && selectedTime !== (user.notification_time || '09:00');

  // 【ローディング表示】
  if (isLoading) {
    return (
      <div className="flex flex-col h-screen">
        <div className="flex-1 flex items-center justify-center">
          <Loading message="設定を読み込み中..." />
        </div>
        <Navigation />
      </div>
    );
  }

  // 【エラー表示（ユーザー取得失敗）】
  if (error && !user) {
    return (
      <div className="flex flex-col h-screen">
        <div className="flex-1 flex items-center justify-center p-4">
          <Error message={error} onRetry={fetchUser} />
        </div>
        <Navigation />
      </div>
    );
  }

  return (
    <div className="flex flex-col min-h-screen pb-20">
      <header className="bg-white shadow-sm p-4 mb-4">
        <h1 className="text-xl font-bold text-gray-800" data-testid="settings-title">
          設定
        </h1>
      </header>

      <main className="flex-1 px-4">
        {/* 成功メッセージ */}
        {successMessage && (
          <div
            className="mb-4 p-3 bg-green-100 border border-green-300 text-green-700 rounded-lg"
            data-testid="success-message"
          >
            {successMessage}
          </div>
        )}

        {/* エラーメッセージ */}
        {error && (
          <div
            className="mb-4 p-3 bg-red-100 border border-red-300 text-red-700 rounded-lg"
            data-testid="error-message"
          >
            {error}
          </div>
        )}

        {/* 通知設定セクション */}
        <section className="bg-white rounded-lg shadow p-4 mb-6" data-testid="notification-section">
          <h2 className="text-lg font-semibold text-gray-800 mb-4">
            通知設定
          </h2>

          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              復習通知時間
            </label>
            <p className="text-sm text-gray-500 mb-3">
              毎日この時間にLINEで復習のリマインドを送信します
            </p>

            <div className="space-y-2" role="radiogroup" aria-label="通知時間選択">
              {NOTIFICATION_TIMES.map((time) => (
                <label
                  key={time.value}
                  className={`flex items-center p-3 rounded-lg border cursor-pointer min-h-[44px] transition-colors ${
                    selectedTime === time.value
                      ? 'border-blue-500 bg-blue-50'
                      : 'border-gray-300 hover:bg-gray-50'
                  }`}
                  data-testid={`time-option-${time.value}`}
                >
                  <input
                    type="radio"
                    name="notifyTime"
                    value={time.value}
                    checked={selectedTime === time.value}
                    onChange={(e) => setSelectedTime(e.target.value)}
                    className="sr-only"
                    aria-label={time.label}
                  />
                  <div
                    className={`w-5 h-5 rounded-full border-2 mr-3 flex items-center justify-center ${
                      selectedTime === time.value
                        ? 'border-blue-500'
                        : 'border-gray-400'
                    }`}
                  >
                    {selectedTime === time.value && (
                      <div className="w-3 h-3 rounded-full bg-blue-500" />
                    )}
                  </div>
                  <span className="text-gray-800">{time.label}</span>
                </label>
              ))}
            </div>
          </div>

          <button
            onClick={handleSave}
            disabled={!hasChanges || isSaving}
            className={`w-full py-3 rounded-lg font-medium min-h-[44px] transition-colors ${
              hasChanges && !isSaving
                ? 'bg-blue-600 text-white hover:bg-blue-700'
                : 'bg-gray-300 text-gray-500 cursor-not-allowed'
            }`}
            data-testid="save-button"
          >
            {isSaving ? '保存中...' : '設定を保存'}
          </button>
        </section>

        {/* アカウント情報セクション */}
        <section className="bg-white rounded-lg shadow p-4 mb-6" data-testid="account-section">
          <h2 className="text-lg font-semibold text-gray-800 mb-4">
            アカウント
          </h2>

          <div className="py-3 border-b border-gray-200">
            <span className="text-sm text-gray-600">メールアドレス</span>
            <p className="text-gray-800 mt-1" data-testid="user-email">
              {user?.email || '-'}
            </p>
          </div>

          <div className="py-3">
            <span className="text-sm text-gray-600">表示名</span>
            <p className="text-gray-800 mt-1" data-testid="user-name">
              {user?.display_name || '-'}
            </p>
          </div>
        </section>

        {/* LINE連携セクション */}
        <section className="bg-white rounded-lg shadow p-4 mb-6" data-testid="line-section">
          <h2 className="text-lg font-semibold text-gray-800 mb-4">
            LINE連携
          </h2>

          <Link
            to="/link-line"
            className="flex items-center justify-between py-3 text-blue-600 hover:text-blue-800 min-h-[44px]"
            data-testid="line-link-button"
          >
            <span>LINE連携設定</span>
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </Link>

          {user?.line_user_id && (
            <p className="text-sm text-green-600 mt-2" data-testid="line-connected">
              連携済み
            </p>
          )}
        </section>

        {/* ログアウトボタン */}
        <button
          onClick={handleLogout}
          disabled={isLoggingOut}
          className="w-full py-3 text-red-600 border border-red-600 rounded-lg hover:bg-red-50 min-h-[44px] transition-colors"
          data-testid="logout-button"
        >
          {isLoggingOut ? 'ログアウト中...' : 'ログアウト'}
        </button>
      </main>

      <Navigation />
    </div>
  );
};
