/**
 * ブラウザプロファイル管理コンポーネント
 * 認証が必要なページへのアクセス用プロファイルの一覧・追加・削除
 */
import { useState, useEffect, useCallback } from 'react';
import { browserProfilesApi } from '@/services/api';
import type { BrowserProfile } from '@/types';

interface BrowserProfileSettingsProps {
  selectedProfileId: string | null;
  onProfileSelect: (profileId: string | null) => void;
  disabled?: boolean;
}

export const BrowserProfileSettings = ({
  selectedProfileId,
  onProfileSelect,
  disabled = false,
}: BrowserProfileSettingsProps) => {
  const [profiles, setProfiles] = useState<BrowserProfile[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [newProfileName, setNewProfileName] = useState('');
  const [showAddForm, setShowAddForm] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchProfiles = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const result = await browserProfilesApi.getProfiles();
      setProfiles(result);
    } catch {
      setError('プロファイルの取得に失敗しました');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchProfiles();
  }, [fetchProfiles]);

  const handleCreate = async () => {
    const name = newProfileName.trim();
    if (!name) return;

    setIsCreating(true);
    setError(null);
    try {
      await browserProfilesApi.createProfile(name);
      setNewProfileName('');
      setShowAddForm(false);
      await fetchProfiles();
    } catch {
      setError('プロファイルの作成に失敗しました');
    } finally {
      setIsCreating(false);
    }
  };

  const handleDelete = async (profileId: string) => {
    setError(null);
    try {
      await browserProfilesApi.deleteProfile(profileId);
      if (selectedProfileId === profileId) {
        onProfileSelect(null);
      }
      await fetchProfiles();
    } catch {
      setError('プロファイルの削除に失敗しました');
    }
  };

  return (
    <div className="space-y-3" data-testid="browser-profile-settings">
      <div className="flex items-center justify-between">
        <label className="text-sm font-medium text-gray-700">
          認証プロファイル
        </label>
        {!showAddForm && (
          <button
            onClick={() => setShowAddForm(true)}
            disabled={disabled}
            className="text-xs text-blue-600 hover:text-blue-800 disabled:text-gray-400"
            data-testid="add-profile-button"
          >
            + 追加
          </button>
        )}
      </div>

      {error && (
        <p className="text-xs text-red-500" data-testid="profile-error">
          {error}
        </p>
      )}

      {showAddForm && (
        <div className="flex gap-2" data-testid="add-profile-form">
          <input
            type="text"
            value={newProfileName}
            onChange={(e) => setNewProfileName(e.target.value)}
            placeholder="プロファイル名"
            maxLength={100}
            className="flex-1 px-2 py-1 text-sm border border-gray-300 rounded focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
            disabled={isCreating}
            data-testid="profile-name-input"
          />
          <button
            onClick={handleCreate}
            disabled={isCreating || !newProfileName.trim()}
            className="px-3 py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:bg-gray-300 disabled:text-gray-500"
            data-testid="save-profile-button"
          >
            {isCreating ? '...' : '保存'}
          </button>
          <button
            onClick={() => {
              setShowAddForm(false);
              setNewProfileName('');
            }}
            disabled={isCreating}
            className="px-3 py-1 text-sm text-gray-600 hover:text-gray-800"
          >
            取消
          </button>
        </div>
      )}

      {isLoading ? (
        <p className="text-sm text-gray-500">読み込み中...</p>
      ) : (
        <div className="space-y-1">
          <button
            onClick={() => onProfileSelect(null)}
            disabled={disabled}
            className={`w-full text-left px-3 py-2 text-sm rounded transition-colors ${
              selectedProfileId === null
                ? 'bg-blue-50 text-blue-700 border border-blue-200'
                : 'text-gray-600 hover:bg-gray-50 border border-transparent'
            }`}
            data-testid="profile-option-none"
          >
            なし（公開ページのみ）
          </button>

          {profiles.map((profile) => (
            <div
              key={profile.profile_id}
              className={`flex items-center justify-between px-3 py-2 text-sm rounded transition-colors ${
                selectedProfileId === profile.profile_id
                  ? 'bg-blue-50 text-blue-700 border border-blue-200'
                  : 'text-gray-600 hover:bg-gray-50 border border-transparent'
              }`}
            >
              <button
                onClick={() => onProfileSelect(profile.profile_id)}
                disabled={disabled}
                className="flex-1 text-left"
                data-testid={`profile-option-${profile.profile_id}`}
              >
                {profile.name}
              </button>
              <button
                onClick={() => handleDelete(profile.profile_id)}
                disabled={disabled}
                className="ml-2 text-xs text-red-400 hover:text-red-600 disabled:text-gray-300"
                data-testid={`delete-profile-${profile.profile_id}`}
              >
                削除
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
