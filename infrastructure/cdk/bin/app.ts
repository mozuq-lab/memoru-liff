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
    }),

    new KeycloakStack(app, 'MemoruKeycloakDev', {
      environment: 'dev',
      domainName: 'keycloak-dev.example.com', // dev はカスタムドメイン未使用（プレースホルダ可）
      // certificateArn: not required for dev
      // hostedZoneId: not required for dev
    }),

    new LiffHostingStack(app, 'MemoruLiffHostingDev', {
      environment: 'dev',
      // domainName: optional for dev (uses CloudFront domain)
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

  const prodStacks = [
    new CognitoStack(app, 'MemoruCognitoProd', {
      environment: 'prod',
      cognitoDomainPrefix: prod.cognitoDomainPrefix,
      callbackUrls: prod.callbackUrls,
      logoutUrls: prod.logoutUrls,
      lineLoginChannelId: process.env.LINE_LOGIN_CHANNEL_ID,
      // prod は Secrets Manager 必須 (CognitoStack 側で平文を弾く)
      lineLoginChannelSecretName: process.env.LINE_LOGIN_CHANNEL_SECRET_NAME,
    }),

    new KeycloakStack(app, 'MemoruKeycloakProd', {
      environment: 'prod',
      domainName: prod.keycloakDomain,
      hostedZoneName: prod.hostedZoneName,
      certificateArn: prod.keycloakCertArn,
      hostedZoneId: prod.hostedZoneId,
    }),

    new LiffHostingStack(app, 'MemoruLiffHostingProd', {
      environment: 'prod',
      domainName: prod.liffDomain,
      hostedZoneName: prod.hostedZoneName,
      certificateArn: prod.liffCertArn,
      hostedZoneId: prod.hostedZoneId,
    }),
  ];
  prodStacks.forEach((s) => cdk.Tags.of(s).add('Environment', 'prod'));
}

app.synth();
