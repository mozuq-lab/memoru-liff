/**
 * 【フィクスチャ概要】: 認証状態のセットアップ
 * 【テスト対応】: TASK-0020 E2Eテスト用フィクスチャ
 */
import { test as base, Page } from '@playwright/test';

// テスト用のモックトークン（JWT形式）
const MOCK_ACCESS_TOKEN =
  'eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0LXVzZXItaWQiLCJlbWFpbCI6InRlc3RAZXhhbXBsZS5jb20iLCJuYW1lIjoi44OG44K544OI44Om44O844K244O8IiwiZXhwIjoxOTk5OTk5OTk5LCJpYXQiOjE3MDAwMDAwMDB9.mock-signature';

const MOCK_USER = {
  user_id: 'test-user-id',
  email: 'test@example.com',
  display_name: 'テストユーザー',
  notification_time: '09:00',
  line_user_id: undefined,
};

/**
 * 認証済みページを提供するカスタムフィクスチャ
 */
export const test = base.extend<{
  authenticatedPage: Page;
}>({
  authenticatedPage: async ({ page }, use) => {
    // API モックのセットアップ
    await setupApiMocks(page);

    // 認証済み状態をセットアップ
    await page.addInitScript((token) => {
      // OIDC用のストレージキーにトークンを設定
      const oidcStorageKey = 'oidc.user:https://keycloak.example.com/realms/memoru:memoru-liff';
      const oidcUser = {
        access_token: token,
        token_type: 'Bearer',
        expires_at: 9999999999,
        profile: {
          sub: 'test-user-id',
          email: 'test@example.com',
          name: 'テストユーザー',
        },
      };
      sessionStorage.setItem(oidcStorageKey, JSON.stringify(oidcUser));
    }, MOCK_ACCESS_TOKEN);

    await use(page);
  },
});

/**
 * APIモックをセットアップ
 */
async function setupApiMocks(page: Page) {
  // ユーザー情報取得API
  await page.route('**/api/users/me', (route) => {
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(MOCK_USER),
    });
  });

  // カード一覧取得API
  await page.route('**/api/cards', (route) => {
    if (route.request().method() === 'GET') {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          cards: [
            {
              card_id: 'card-1',
              user_id: 'test-user-id',
              front: '表面テスト',
              back: '裏面テスト',
              next_review: new Date().toISOString(),
              ease_factor: 2.5,
              interval: 1,
              review_count: 0,
              created_at: new Date().toISOString(),
              updated_at: new Date().toISOString(),
            },
          ],
          count: 1,
        }),
      });
    } else {
      route.continue();
    }
  });

  // 復習カード取得API
  await page.route('**/api/reviews/due', (route) => {
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        cards: [],
        count: 0,
      }),
    });
  });
}

export { expect } from '@playwright/test';
