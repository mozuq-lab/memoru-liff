import { resolveProdConfig } from '../lib/prod-config';

/** 全ての必須変数が揃った有効な env セット。 */
function validEnv(): NodeJS.ProcessEnv {
  return {
    MEMORU_PROD_HOSTED_ZONE_NAME: 'memoru.app',
    MEMORU_PROD_HOSTED_ZONE_ID: 'ZABCDEFGHIJKLM',
    MEMORU_PROD_KEYCLOAK_DOMAIN: 'keycloak.memoru.app',
    MEMORU_PROD_KEYCLOAK_CERT_ARN:
      'arn:aws:acm:ap-northeast-1:999988887777:certificate/aaaa-bbbb',
    MEMORU_PROD_LIFF_DOMAIN: 'liff.memoru.app',
    MEMORU_PROD_LIFF_CERT_ARN:
      'arn:aws:acm:us-east-1:999988887777:certificate/cccc-dddd',
    MEMORU_PROD_COGNITO_DOMAIN_PREFIX: 'memoru-prod-app',
    MEMORU_PROD_CALLBACK_URLS:
      'https://liff.memoru.app/callback,https://liff.memoru.app/',
    MEMORU_PROD_LOGOUT_URLS: 'https://liff.memoru.app/',
    LINE_LOGIN_CHANNEL_ID: '2001234567',
    LINE_LOGIN_CHANNEL_SECRET_NAME: 'memoru-prod-line-channel-secret',
  };
}

describe('resolveProdConfig', () => {
  describe('正常系', () => {
    test('全変数が揃っていれば ProdConfig を返す', () => {
      const cfg = resolveProdConfig(validEnv());
      expect(cfg.hostedZoneName).toBe('memoru.app');
      expect(cfg.hostedZoneId).toBe('ZABCDEFGHIJKLM');
      expect(cfg.keycloakDomain).toBe('keycloak.memoru.app');
      expect(cfg.liffDomain).toBe('liff.memoru.app');
      expect(cfg.cognitoDomainPrefix).toBe('memoru-prod-app');
      expect(cfg.lineLoginChannelId).toBe('2001234567');
      expect(cfg.lineLoginChannelSecretName).toBe(
        'memoru-prod-line-channel-secret',
      );
    });

    test('LINE Login の 2 値が未設定なら不足として列挙される', () => {
      // cognito-stack は両値が揃わないと LINE IdP を作成しないため、
      // ガード無しでは「LINE ログイン抜けの User Pool」を黙ってデプロイできてしまう
      const env = validEnv();
      delete env.LINE_LOGIN_CHANNEL_ID;
      delete env.LINE_LOGIN_CHANNEL_SECRET_NAME;
      expect(() => resolveProdConfig(env)).toThrow(/LINE_LOGIN_CHANNEL_ID/);
      expect(() => resolveProdConfig(env)).toThrow(
        /LINE_LOGIN_CHANNEL_SECRET_NAME/,
      );
    });

    test('LINE Login シークレット名のプレースホルダは拒否される', () => {
      const env = validEnv();
      env.LINE_LOGIN_CHANNEL_SECRET_NAME = '<your-secret-name>';
      expect(() => resolveProdConfig(env)).toThrow(
        /プレースホルダ[\s\S]*LINE_LOGIN_CHANNEL_SECRET_NAME/,
      );
    });

    test('カンマ区切りの URL がリストに分割される', () => {
      const cfg = resolveProdConfig(validEnv());
      expect(cfg.callbackUrls).toEqual([
        'https://liff.memoru.app/callback',
        'https://liff.memoru.app/',
      ]);
      expect(cfg.logoutUrls).toEqual(['https://liff.memoru.app/']);
    });

    test('URL 周囲の空白がトリムされる', () => {
      const env = validEnv();
      env.MEMORU_PROD_CALLBACK_URLS =
        ' https://liff.memoru.app/callback , https://liff.memoru.app/ ';
      const cfg = resolveProdConfig(env);
      expect(cfg.callbackUrls).toEqual([
        'https://liff.memoru.app/callback',
        'https://liff.memoru.app/',
      ]);
    });
  });

  describe('必須変数の欠落', () => {
    test('1 変数欠落時に throw し、変数名を列挙する', () => {
      const env = validEnv();
      delete env.MEMORU_PROD_KEYCLOAK_DOMAIN;
      expect(() => resolveProdConfig(env)).toThrow(
        /MEMORU_PROD_KEYCLOAK_DOMAIN/,
      );
    });

    test('全変数欠落時に全変数名を列挙する', () => {
      let message = '';
      try {
        resolveProdConfig({});
      } catch (e) {
        message = (e as Error).message;
      }
      expect(message).toContain('MEMORU_PROD_HOSTED_ZONE_NAME');
      expect(message).toContain('MEMORU_PROD_HOSTED_ZONE_ID');
      expect(message).toContain('MEMORU_PROD_KEYCLOAK_DOMAIN');
      expect(message).toContain('MEMORU_PROD_KEYCLOAK_CERT_ARN');
      expect(message).toContain('MEMORU_PROD_LIFF_DOMAIN');
      expect(message).toContain('MEMORU_PROD_LIFF_CERT_ARN');
      expect(message).toContain('MEMORU_PROD_COGNITO_DOMAIN_PREFIX');
      expect(message).toContain('MEMORU_PROD_CALLBACK_URLS');
      expect(message).toContain('MEMORU_PROD_LOGOUT_URLS');
    });

    test('空文字列は未設定として扱う', () => {
      const env = validEnv();
      env.MEMORU_PROD_LIFF_DOMAIN = '   ';
      expect(() => resolveProdConfig(env)).toThrow(/MEMORU_PROD_LIFF_DOMAIN/);
    });

    test('リスト変数がカンマのみ等で空になる場合は未設定扱い', () => {
      const env = validEnv();
      env.MEMORU_PROD_CALLBACK_URLS = ' , , ';
      expect(() => resolveProdConfig(env)).toThrow(/MEMORU_PROD_CALLBACK_URLS/);
    });
  });

  describe('プレースホルダ検出', () => {
    test('example.com を含む値を拒否する', () => {
      const env = validEnv();
      env.MEMORU_PROD_KEYCLOAK_DOMAIN = 'keycloak.example.com';
      expect(() => resolveProdConfig(env)).toThrow(
        /MEMORU_PROD_KEYCLOAK_DOMAIN/,
      );
    });

    test('placeholder を含む証明書 ARN を拒否する', () => {
      const env = validEnv();
      env.MEMORU_PROD_LIFF_CERT_ARN =
        'arn:aws:acm:us-east-1:123456789012:certificate/placeholder';
      expect(() => resolveProdConfig(env)).toThrow(/MEMORU_PROD_LIFF_CERT_ARN/);
    });

    test('ダミー HostedZone ID を拒否する', () => {
      const env = validEnv();
      env.MEMORU_PROD_HOSTED_ZONE_ID = 'Z0123456789ABCDEF';
      expect(() => resolveProdConfig(env)).toThrow(
        /MEMORU_PROD_HOSTED_ZONE_ID/,
      );
    });

    test('プレースホルダを含む callback URL を拒否する', () => {
      const env = validEnv();
      env.MEMORU_PROD_CALLBACK_URLS = 'https://liff.example.com/callback';
      expect(() => resolveProdConfig(env)).toThrow(
        /MEMORU_PROD_CALLBACK_URLS/,
      );
    });

    test('エラーメッセージにプレースホルダ見出しが含まれる', () => {
      const env = validEnv();
      env.MEMORU_PROD_LIFF_DOMAIN = 'liff.example.com';
      expect(() => resolveProdConfig(env)).toThrow(/プレースホルダ/);
    });
  });

  describe('証明書 ARN のリージョン検証', () => {
    test('Keycloak 証明書が ap-northeast-1 でないと拒否する', () => {
      const env = validEnv();
      env.MEMORU_PROD_KEYCLOAK_CERT_ARN =
        'arn:aws:acm:us-east-1:999988887777:certificate/aaaa-bbbb';
      expect(() => resolveProdConfig(env)).toThrow(
        /MEMORU_PROD_KEYCLOAK_CERT_ARN/,
      );
    });

    test('LIFF 証明書が us-east-1 でないと拒否する（CloudFront 要件）', () => {
      const env = validEnv();
      env.MEMORU_PROD_LIFF_CERT_ARN =
        'arn:aws:acm:ap-northeast-1:999988887777:certificate/cccc-dddd';
      expect(() => resolveProdConfig(env)).toThrow(/MEMORU_PROD_LIFF_CERT_ARN/);
    });
  });
});
