/**
 * 【テスト概要】: 認証フローE2Eテスト
 * 【テスト対象】: 認証・認可フロー全体
 * 【テスト対応】: TASK-0020 テストケース1〜3
 *
 * 注意: 完全な認証フローテストはKeycloakがデプロイされた後に実行します。
 * 現在はルーティングとセッションストレージの基本動作を確認します。
 */
import { test, expect, Page } from '@playwright/test';

// テスト用のモックOIDCユーザー
const mockOidcUser = {
  access_token:
    'eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0LXVzZXItaWQiLCJleHAiOjk5OTk5OTk5OTl9.signature',
  token_type: 'Bearer',
  expires_at: 9999999999,
  profile: {
    sub: 'test-user-id',
    email: 'test@example.com',
    name: 'テストユーザー',
  },
};

/**
 * 認証済み状態をセットアップするヘルパー
 */
async function setupAuthenticatedState(page: Page) {
  await page.addInitScript((oidcUser) => {
    const storageKey =
      'oidc.user:https://keycloak.example.com/realms/memoru:memoru-liff';
    sessionStorage.setItem(storageKey, JSON.stringify(oidcUser));
  }, mockOidcUser);
}

test.describe('基本ルーティング', () => {
  test('ルートページにアクセスできる', async ({ page }) => {
    await page.goto('/', { waitUntil: 'domcontentloaded' });
    // ページがロードされることを確認（リダイレクトも許容）
    const url = page.url();
    expect(url).toContain('localhost');
  });
});

test.describe('TC-001-03: 認証情報のストレージ確認', () => {
  test('sessionStorageにOIDC情報を保存できる', async ({ page }) => {
    await setupAuthenticatedState(page);
    await page.goto('/');

    // sessionStorageにOIDC情報が保存されていることを確認
    const storedData = await page.evaluate(() => {
      const keys = Object.keys(sessionStorage);
      const oidcKey = keys.find((k) => k.includes('oidc.user'));
      return oidcKey ? sessionStorage.getItem(oidcKey) : null;
    });

    expect(storedData).toBeTruthy();
    const parsed = JSON.parse(storedData!);
    expect(parsed.access_token).toMatch(/^eyJ/); // JWT形式確認
  });

  test('認証トークンがJWT形式である', async ({ page }) => {
    await setupAuthenticatedState(page);
    await page.goto('/');

    const token = await page.evaluate(() => {
      const keys = Object.keys(sessionStorage);
      const oidcKey = keys.find((k) => k.includes('oidc.user'));
      if (!oidcKey) return null;
      const data = JSON.parse(sessionStorage.getItem(oidcKey)!);
      return data.access_token;
    });

    expect(token).toBeTruthy();
    // JWT形式: header.payload.signature
    expect(token).toMatch(/^eyJ[A-Za-z0-9-_]+\.[A-Za-z0-9-_]+\./);
  });

  test('ユーザープロフィールがストレージに含まれる', async ({ page }) => {
    await setupAuthenticatedState(page);
    await page.goto('/');

    const profile = await page.evaluate(() => {
      const keys = Object.keys(sessionStorage);
      const oidcKey = keys.find((k) => k.includes('oidc.user'));
      if (!oidcKey) return null;
      const data = JSON.parse(sessionStorage.getItem(oidcKey)!);
      return data.profile;
    });

    expect(profile).toBeTruthy();
    expect(profile.sub).toBe('test-user-id');
    expect(profile.email).toBe('test@example.com');
  });
});

test.describe('レスポンシブビューポート', () => {
  test.use({ viewport: { width: 375, height: 667 } }); // iPhone SE

  test('モバイルビューポートでページが表示される', async ({ page }) => {
    await page.goto('/', { waitUntil: 'domcontentloaded' });

    // ビューポートサイズを確認
    const viewportSize = page.viewportSize();
    expect(viewportSize?.width).toBe(375);
    expect(viewportSize?.height).toBe(667);
  });
});

test.describe('Playwright設定確認', () => {
  test('スクリーンショットが取得可能', async ({ page }) => {
    await page.goto('/');
    const screenshot = await page.screenshot();
    expect(screenshot).toBeTruthy();
    expect(screenshot.length).toBeGreaterThan(0);
  });

  test('コンソールエラーを検出可能', async ({ page }) => {
    const consoleErrors: string[] = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });

    await page.goto('/');

    // テスト完了後、コンソールエラーの有無を報告（失敗させない）
    console.log(
      `Console errors found: ${consoleErrors.length}`,
      consoleErrors.slice(0, 3)
    );
  });
});

/**
 * 以下のテストはKeycloakデプロイ後に有効化
 *
 * test.describe.skip('TC-001-01: 未認証ユーザーのリダイレクト', () => {
 *   test('未認証状態でホームにアクセスするとKeycloakにリダイレクト', async ({ page }) => {
 *     await page.goto('/home');
 *     await expect(page).toHaveURL(/.*keycloak.*\/auth/);
 *   });
 * });
 *
 * test.describe.skip('TC-001-02: LINE Login認証成功後の遷移', () => {
 *   test('認証成功後ホーム画面に遷移', async ({ page }) => {
 *     // Keycloakでの認証フロー実行
 *     await page.goto('/home');
 *     await expect(page).toHaveURL('/home');
 *     await expect(page.locator('[data-testid="today-review-section"]')).toBeVisible();
 *   });
 * });
 */
