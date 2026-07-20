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
  /**
   * PreSignUp トリガー Lambda（SAM backend が所有）の ARN。CognitoStack に渡して
   * サインアップ許可リストのトリガーとして配線する。`BOOTSTRAP-NO-TRIGGER` センチネル
   * 指定時（初回ブートストラップ専用）は undefined になり、トリガーなしで synth する。
   */
  preSignUpLambdaArn?: string;
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

// PreSignUp トリガー Lambda の ARN。VarSpec テーブル（単純な必須/プレースホルダ判定のみ）
// には収まらない専用ロジック（センチネル許容 + ARN 形式検証）が必要なため、
// REQUIRED_VARS には含めずループ外で個別に処理する。
const PRESIGNUP_LAMBDA_ARN_ENV = 'MEMORU_PROD_PRESIGNUP_LAMBDA_ARN';
/**
 * 初回ブートストラップ専用のセンチネル値。SAM backend（PreSignupFunction）より先に
 * CDK Cognito スタックを作る必要があるための逃げ道。明示的・greppable な値にすることで
 * 無自覚なフェイルオープン（トリガー未配線のまま prod 運用）を防ぐ。
 * 既存 PLACEHOLDER_PATTERNS に一致しないことを確認済み。
 */
const PRESIGNUP_BOOTSTRAP_SENTINEL = 'BOOTSTRAP-NO-TRIGGER';
const PRESIGNUP_LAMBDA_ARN_PREFIX = 'arn:aws:lambda:ap-northeast-1:';

function isPlaceholder(value: string): boolean {
  return PLACEHOLDER_PATTERNS.some((p) => p.test(value));
}

function isValidPreSignUpLambdaArn(value: string): boolean {
  return value.startsWith(PRESIGNUP_LAMBDA_ARN_PREFIX) && value.includes(':function:');
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
  const invalidFormat: string[] = [];

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

  // PreSignUp トリガー Lambda ARN: VarSpec テーブルに収まらないため個別処理する。
  // センチネル判定を最初に行い、それ以外はプレースホルダ検出 + ARN 形式検証を行う。
  let preSignUpLambdaArn: string | undefined;
  const rawPreSignUp = (env[PRESIGNUP_LAMBDA_ARN_ENV] ?? '').trim();
  if (rawPreSignUp.length === 0) {
    missing.push(PRESIGNUP_LAMBDA_ARN_ENV);
  } else if (rawPreSignUp === PRESIGNUP_BOOTSTRAP_SENTINEL) {
    // 非 TTY の `cdk synth`（CI 等）では console.warn の出力が失われ、運用者が
    // 気づけないことが実証されている。警告は呼び出し元（cognito-stack.ts）で
    // cdk.Annotations.of(this).addWarning() を使って出す（synth 結果の一部として
    // 確実に残る）。ここでは undefined を返す（トリガーなしで synth する）だけに留める。
    preSignUpLambdaArn = undefined;
  } else if (isPlaceholder(rawPreSignUp)) {
    placeholders.push(PRESIGNUP_LAMBDA_ARN_ENV);
  } else if (!isValidPreSignUpLambdaArn(rawPreSignUp)) {
    invalidFormat.push(PRESIGNUP_LAMBDA_ARN_ENV);
  } else {
    preSignUpLambdaArn = rawPreSignUp;
  }

  if (
    missing.length > 0
    || placeholders.length > 0
    || wrongRegion.length > 0
    || invalidFormat.length > 0
  ) {
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
    if (invalidFormat.length > 0) {
      lines.push(
        '',
        `[Lambda ARN 形式が不正な変数（${PRESIGNUP_LAMBDA_ARN_PREFIX}... 形式かつ :function: を含む必要あり）]`,
        ...invalidFormat.map((f) => `  - ${f}`),
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
    preSignUpLambdaArn,
    apiEndpoint: resolved.apiEndpoint as string,
  };
}
