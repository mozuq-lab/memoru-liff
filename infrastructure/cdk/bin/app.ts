#!/usr/bin/env node
import * as cdk from 'aws-cdk-lib';
import { CognitoStack } from '../lib/cognito-stack';
import { KeycloakStack } from '../lib/keycloak-stack';
import { LiffHostingStack } from '../lib/liff-hosting-stack';

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
if (!stage || stage === 'dev') {
  const devStacks = [
    new CognitoStack(app, 'MemoruCognitoDev', {
      environment: 'dev',
      cognitoDomainPrefix: 'memoru-dev', // TODO: Replace with actual domain prefix
      callbackUrls: ['http://localhost:3000/callback', 'https://localhost:3000/callback'],
      logoutUrls: ['http://localhost:3000/', 'https://localhost:3000/'],
      // TODO: prod 環境では AWS Secrets Manager の Dynamic Reference に移行する
      lineLoginChannelId: process.env.LINE_LOGIN_CHANNEL_ID,
      lineLoginChannelSecret: process.env.LINE_LOGIN_CHANNEL_SECRET,
    }),

    new KeycloakStack(app, 'MemoruKeycloakDev', {
      environment: 'dev',
      domainName: 'keycloak-dev.example.com', // TODO: Replace with actual domain
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
if (stage === 'prod') {
  const prodStacks = [
    new CognitoStack(app, 'MemoruCognitoProd', {
      environment: 'prod',
      cognitoDomainPrefix: 'memoru-prod', // TODO: Replace with actual domain prefix
      callbackUrls: ['https://liff.example.com/callback'], // TODO: Replace with actual URLs
      logoutUrls: ['https://liff.example.com/'], // TODO: Replace with actual URLs
      // TODO: AWS Secrets Manager の Dynamic Reference に移行する
      lineLoginChannelId: process.env.LINE_LOGIN_CHANNEL_ID,
      lineLoginChannelSecret: process.env.LINE_LOGIN_CHANNEL_SECRET,
    }),

    new KeycloakStack(app, 'MemoruKeycloakProd', {
      environment: 'prod',
      domainName: 'keycloak.example.com', // TODO: Replace with actual domain
      hostedZoneName: 'example.com', // TODO: Replace with actual hosted zone name
      certificateArn: 'arn:aws:acm:ap-northeast-1:123456789012:certificate/placeholder', // TODO: Replace with actual certificate ARN
      hostedZoneId: 'Z0123456789ABCDEF', // TODO: Replace with actual hosted zone ID
    }),

    new LiffHostingStack(app, 'MemoruLiffHostingProd', {
      environment: 'prod',
      domainName: 'liff.example.com', // TODO: Replace with actual domain
      hostedZoneName: 'example.com', // TODO: Replace with actual hosted zone name
      certificateArn: 'arn:aws:acm:us-east-1:123456789012:certificate/placeholder', // TODO: Replace with actual certificate ARN (must be us-east-1)
      hostedZoneId: 'Z0123456789ABCDEF', // TODO: Replace with actual hosted zone ID
    }),
  ];
  prodStacks.forEach((s) => cdk.Tags.of(s).add('Environment', 'prod'));
}

app.synth();
