/**
 * prod 環境のデプロイ値を環境変数から外部注入するためのリゾルバ。
 *
 * 背景: 本リポジトリは public のため、prod の実環境値（ドメイン・証明書 ARN・
 * HostedZone・Cognito ドメイン等）を Git にコミットしない方針。これらは
 * デプロイ実行者のローカル環境変数 / GitHub Environments からのみ供給される。
 *
 * resolveProdConfig() は必須変数の欠落と、example.com / placeholder 等の
 * プレースホルダ値の混入を検出し、不足/不正な変数名を列挙した明確なエラーで
 * synth / deploy を中断する。
 */

export interface ProdConfig {
  hostedZoneName: string;
  hostedZoneId: string;
  keycloakDomain: string;
  keycloakCertArn: string;
  liffDomain: string;
  liffCertArn: string;
  cognitoDomainPrefix: string;
  callbackUrls: string[];
  logoutUrls: string[];
  lineLoginChannelId: string;
  lineLoginChannelSecretName: string;
  /**
   * バックエンド API のオリジン（例: https://xxxx.execute-api.ap-northeast-1.amazonaws.com）。
   * LiffHostingStack の CSP connect-src に配線する。未設定だとブラウザが API への
   * fetch を CSP でブロックし、アプリ全体が動作しなくなるため prod では必須。
   * オリジン（scheme + host[:port]）のみを指定し、ステージパス等は含めない。
   */
  apiEndpoint: string;
}

/** 値が「未設定 or プレースホルダ」かを判定するためのパターン。 */
const PLACEHOLDER_PATTERNS: RegExp[] = [
  /example\.com/i,
  /placeholder/i,
  /your-domain/i,
  /xxxx/i,
  /<[^>]+>/, // <ACCOUNT_ID> のようなテンプレート記法
  /123456789012/, // ダミー AWS アカウント ID
  /Z0123456789ABCDEF/i, // ダミー HostedZone ID
  /TODO/i,
];

interface VarSpec {
  /** 環境変数名 */
  env: string;
  /** ProdConfig 上のフィールド名 */
  key: keyof ProdConfig | 'callbackUrls' | 'logoutUrls';
  /** 期待する ARN リージョン（証明書の場合のみ）。不一致は拒否する。 */
  certRegion?: 'ap-northeast-1' | 'us-east-1';
  /** カンマ区切りのリストとして解釈する。 */
  list?: boolean;
}

const REQUIRED_VARS: VarSpec[] = [
  { env: 'MEMORU_PROD_HOSTED_ZONE_NAME', key: 'hostedZoneName' },
  { env: 'MEMORU_PROD_HOSTED_ZONE_ID', key: 'hostedZoneId' },
  { env: 'MEMORU_PROD_KEYCLOAK_DOMAIN', key: 'keycloakDomain' },
  {
    env: 'MEMORU_PROD_KEYCLOAK_CERT_ARN',
    key: 'keycloakCertArn',
    certRegion: 'ap-northeast-1',
  },
  { env: 'MEMORU_PROD_LIFF_DOMAIN', key: 'liffDomain' },
  {
    env: 'MEMORU_PROD_LIFF_CERT_ARN',
    key: 'liffCertArn',
    certRegion: 'us-east-1',
  },
  { env: 'MEMORU_PROD_COGNITO_DOMAIN_PREFIX', key: 'cognitoDomainPrefix' },
  { env: 'MEMORU_PROD_CALLBACK_URLS', key: 'callbackUrls', list: true },
  { env: 'MEMORU_PROD_LOGOUT_URLS', key: 'logoutUrls', list: true },
  // LINE Login IdP の 2 値も prod では必須。cognito-stack.ts は両方そろわないと
  // LINE IdP を作成しないため、ガード無しだと「LINE ログインが抜けた User Pool」を
  // 気づかずにデプロイできてしまう。
  { env: 'LINE_LOGIN_CHANNEL_ID', key: 'lineLoginChannelId' },
  { env: 'LINE_LOGIN_CHANNEL_SECRET_NAME', key: 'lineLoginChannelSecretName' },
  // CSP connect-src 用の API オリジン。未配線だとブラウザが API fetch を CSP で
  // ブロックするため、prod では必須とする（example.com 等のプレースホルダも拒否）。
  { env: 'MEMORU_PROD_API_ENDPOINT', key: 'apiEndpoint' },
];

function isPlaceholder(value: string): boolean {
  return PLACEHOLDER_PATTERNS.some((p) => p.test(value));
}

/**
 * 環境変数から prod の実環境値を解決する。
 * 必須変数が欠けている / プレースホルダが混入している場合は throw する。
 */
export function resolveProdConfig(
  env: NodeJS.ProcessEnv = process.env,
): ProdConfig {
  const missing: string[] = [];
  const placeholders: string[] = [];
  const wrongRegion: string[] = [];

  const resolved: Record<string, string | string[]> = {};

  for (const spec of REQUIRED_VARS) {
    const raw = (env[spec.env] ?? '').trim();
    if (raw.length === 0) {
      missing.push(spec.env);
      continue;
    }

    if (spec.list) {
      const items = raw
        .split(',')
        .map((s) => s.trim())
        .filter((s) => s.length > 0);
      if (items.length === 0) {
        missing.push(spec.env);
        continue;
      }
      if (items.some((item) => isPlaceholder(item))) {
        placeholders.push(spec.env);
        continue;
      }
      resolved[spec.key] = items;
      continue;
    }

    if (isPlaceholder(raw)) {
      placeholders.push(spec.env);
      continue;
    }

    if (spec.certRegion && !raw.includes(`:${spec.certRegion}:`)) {
      wrongRegion.push(`${spec.env} (must be in ${spec.certRegion})`);
      continue;
    }

    resolved[spec.key] = raw;
  }

  if (missing.length > 0 || placeholders.length > 0 || wrongRegion.length > 0) {
    const lines: string[] = [
      'prod スタックの生成に必要な環境変数が不足/不正です。',
      'public リポジトリのため実環境値はコミットされません。デプロイ前に環境変数を設定してください。',
      '詳細は docs/deployment-guide-prod.md を参照。',
    ];
    if (missing.length > 0) {
      lines.push('', '[未設定の必須変数]', ...missing.map((m) => `  - ${m}`));
    }
    if (placeholders.length > 0) {
      lines.push(
        '',
        '[プレースホルダ値が検出された変数（example.com / placeholder 等は不可）]',
        ...placeholders.map((p) => `  - ${p}`),
      );
    }
    if (wrongRegion.length > 0) {
      lines.push(
        '',
        '[証明書 ARN のリージョンが不正な変数]',
        ...wrongRegion.map((w) => `  - ${w}`),
      );
    }
    throw new Error(lines.join('\n'));
  }

  return {
    hostedZoneName: resolved.hostedZoneName as string,
    hostedZoneId: resolved.hostedZoneId as string,
    keycloakDomain: resolved.keycloakDomain as string,
    keycloakCertArn: resolved.keycloakCertArn as string,
    liffDomain: resolved.liffDomain as string,
    liffCertArn: resolved.liffCertArn as string,
    cognitoDomainPrefix: resolved.cognitoDomainPrefix as string,
    callbackUrls: resolved.callbackUrls as string[],
    logoutUrls: resolved.logoutUrls as string[],
    lineLoginChannelId: resolved.lineLoginChannelId as string,
    lineLoginChannelSecretName: resolved.lineLoginChannelSecretName as string,
    apiEndpoint: resolved.apiEndpoint as string,
  };
}
