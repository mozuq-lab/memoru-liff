#!/usr/bin/env node
import * as cdk from 'aws-cdk-lib';
import { CognitoStack } from '../lib/cognito-stack';
import { KeycloakStack } from '../lib/keycloak-stack';
import { LiffHostingStack } from '../lib/liff-hosting-stack';
import { resolveProdConfig } from '../lib/prod-config';

const app = new cdk.App();

// 全スタック共通タグ
cdk.Tags.of(app).add('Project', 'memoru-liff');
cdk.Tags.of(app).add('ManagedBy', 'cdk');

// 環境フィルタリング: -c stage=dev|prod で synth 対象を制御
// 未指定時は dev のみ（prod のプレースホルダ値による誤デプロイを防止）
const stage = app.node.tryGetContext('stage') as string | undefined;

// L-34: 未知の stage（例: typo や未実装の staging）が指定されると、dev/prod の
// どちらのブランチも実行されずスタック 0 件で synth が無音成功し、誤操作に気づけない。
// 既知の値（未指定 / dev / prod）以外は明示的に失敗させる。staging は未実装のため拒否。
if (stage !== undefined && stage !== 'dev' && stage !== 'prod') {
  throw new Error(
    `Unknown stage: "${stage}". Use -c stage=dev or -c stage=prod (staging is not implemented).`,
  );
}

// ============================================================
// dev 環境
// ============================================================
// NOTE: dev はローカル / CloudFront ドメインで動作する開発用途のため、
//   - cognitoDomainPrefix / callbackUrls は localhost ベースの既定値
//   - Keycloak/LIFF はカスタムドメイン・証明書を要求しない
// いずれも実環境固有の値（証明書 ARN・HostedZone・本番ドメイン）を含まないため、
// public リポジトリにコミットしても問題ない。CloudFront ドメインを callback に
// 追加したい場合は MEMORU_DEV_EXTRA_CALLBACK_URLS / MEMORU_DEV_EXTRA_LOGOUT_URLS
// （カンマ区切り）で外部注入できる（未設定なら従来どおり localhost のみ）。
if (!stage || stage === 'dev') {
  const splitCsv = (v: string | undefined): string[] =>
    (v ?? '')
      .split(',')
      .map((s) => s.trim())
      .filter((s) => s.length > 0);

  const devCallbackUrls = [
    'http://localhost:3000/callback',
    'https://localhost:3000/callback',
    ...splitCsv(process.env.MEMORU_DEV_EXTRA_CALLBACK_URLS),
  ];
  const devLogoutUrls = [
    'http://localhost:3000/',
    'https://localhost:3000/',
    ...splitCsv(process.env.MEMORU_DEV_EXTRA_LOGOUT_URLS),
  ];

  const devStacks = [
    new CognitoStack(app, 'MemoruCognitoDev', {
      environment: 'dev',
      cognitoDomainPrefix: process.env.MEMORU_DEV_COGNITO_DOMAIN_PREFIX ?? 'memoru-dev',
      callbackUrls: devCallbackUrls,
      logoutUrls: devLogoutUrls,
      lineLoginChannelId: process.env.LINE_LOGIN_CHANNEL_ID,
      // dev のみ平文 fallback を許容 (互換性目的)。優先は Secrets Manager 名 / ARN。
      lineLoginChannelSecretName: process.env.LINE_LOGIN_CHANNEL_SECRET_NAME,
      lineLoginChannelSecret: process.env.LINE_LOGIN_CHANNEL_SECRET_NAME
        ? undefined
        : process.env.LINE_LOGIN_CHANNEL_SECRET,
      // サインアップ許可リスト: PreSignUp トリガー Lambda（SAM backend が所有）の ARN。
      // dev は任意（未設定ならトリガーなし＝現状維持）。
      preSignUpLambdaArn: process.env.MEMORU_DEV_PRESIGNUP_LAMBDA_ARN,
    }),

    new KeycloakStack(app, 'MemoruKeycloakDev', {
      environment: 'dev',
      domainName: 'keycloak-dev.example.com', // dev はカスタムドメイン未使用（プレースホルダ可）
      // certificateArn: not required for dev
      // hostedZoneId: not required for dev
      // H-1: 指定すると dev Keycloak ALB の受信を当該 CIDR のみに制限する（未指定なら全公開）。
      albIngressCidr: process.env.MEMORU_DEV_KEYCLOAK_ALLOWED_CIDR,
    }),

    new LiffHostingStack(app, 'MemoruLiffHostingDev', {
      environment: 'dev',
      // domainName: optional for dev (uses CloudFront domain)
      // CSP connect-src に許可する API オリジン（例:
      // https://xxxx.execute-api.ap-northeast-1.amazonaws.com）。実環境固有値の
      // ため環境変数で外部注入する。dev は未設定でも synth 可能（その場合 API への
      // fetch が CSP でブロックされるため、実際に動かすなら設定すること）。
      apiEndpoint: process.env.MEMORU_DEV_API_ENDPOINT,
    }),
  ];
  devStacks.forEach((s) => cdk.Tags.of(s).add('Environment', 'dev'));
}

// ============================================================
// prod 環境
// ============================================================
// 実環境固有の値（ドメイン・証明書 ARN・HostedZone・Cognito ドメイン等）は
// public リポジトリにコミットしない方針のため、環境変数から外部注入する。
// 不足・プレースホルダ混入時は resolveProdConfig() が明確なエラーで synth を中断する。
if (stage === 'prod') {
  const prod = resolveProdConfig(process.env);

  // M-24: Cognito Hosted UI / cognito-idp のホストは region 依存。デプロイ先 region を
  // 環境変数から解決する（未設定時は東京リージョンを既定）。
  const cognitoRegion =
    process.env.CDK_DEFAULT_REGION ?? process.env.AWS_REGION ?? 'ap-northeast-1';

  // prod スタックは誤操作による cdk destroy / CloudFormation スタック削除を防ぐため
  // terminationProtection を有効にする（dev には付けない）。解除はコード変更ではなく
  // CloudFormation コンソール / update-termination-protection で明示的に行う。
  const prodStacks = [
    new CognitoStack(app, 'MemoruCognitoProd', {
      environment: 'prod',
      terminationProtection: true,
      cognitoDomainPrefix: prod.cognitoDomainPrefix,
      callbackUrls: prod.callbackUrls,
      logoutUrls: prod.logoutUrls,
      // LINE Login の 2 値も resolveProdConfig の必須ガードを通った値を使う
      lineLoginChannelId: prod.lineLoginChannelId,
      // prod は Secrets Manager 必須 (CognitoStack 側で平文を弾く)
      lineLoginChannelSecretName: prod.lineLoginChannelSecretName,
      // サインアップ許可リスト: PreSignUp トリガー Lambda（SAM backend が所有）の ARN。
      // resolveProdConfig() が MEMORU_PROD_PRESIGNUP_LAMBDA_ARN の必須化・センチネル
      // (BOOTSTRAP-NO-TRIGGER) 許容・ARN 形式検証を行う。
      preSignUpLambdaArn: prod.preSignUpLambdaArn,
    }),

    new KeycloakStack(app, 'MemoruKeycloakProd', {
      environment: 'prod',
      terminationProtection: true,
      domainName: prod.keycloakDomain,
      hostedZoneName: prod.hostedZoneName,
      certificateArn: prod.keycloakCertArn,
      hostedZoneId: prod.hostedZoneId,
    }),

    new LiffHostingStack(app, 'MemoruLiffHostingProd', {
      environment: 'prod',
      terminationProtection: true,
      domainName: prod.liffDomain,
      hostedZoneName: prod.hostedZoneName,
      certificateArn: prod.liffCertArn,
      hostedZoneId: prod.hostedZoneId,
      // CSP connect-src に許可する API オリジン。resolveProdConfig() が
      // MEMORU_PROD_API_ENDPOINT の必須化とプレースホルダ検証を行う。
      // 未配線だとブラウザが API fetch を CSP でブロックし全機能が停止する。
      apiEndpoint: prod.apiEndpoint,
      // M-24: OIDC IdP のオリジンを CSP connect-src に許可する。Keycloak / Cognito の
      // どちらが authority になっても token/userinfo 取得がブロックされないよう両方を渡す。
      // （Cognito Hosted UI / cognito-idp の両ホストを許可）
      oidcConnectSources: [
        `https://${prod.keycloakDomain}`,
        `https://${prod.cognitoDomainPrefix}.auth.${cognitoRegion}.amazoncognito.com`,
        `https://cognito-idp.${cognitoRegion}.amazonaws.com`,
      ],
    }),
  ];
  prodStacks.forEach((s) => cdk.Tags.of(s).add('Environment', 'prod'));
}

app.synth();
