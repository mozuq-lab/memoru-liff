#!/usr/bin/env node
import * as cdk from 'aws-cdk-lib';
import { CognitoStack } from '../lib/cognito-stack';
import { KeycloakStack } from '../lib/keycloak-stack';
import { LiffHostingStack } from '../lib/liff-hosting-stack';

const app = new cdk.App();

// ============================================================
// dev 環境
// ============================================================
new CognitoStack(app, 'MemoruCognitoDev', {
  environment: 'dev',
  cognitoDomainPrefix: 'memoru-dev', // TODO: Replace with actual domain prefix
  callbackUrls: ['http://localhost:3000/callback', 'https://localhost:3000/callback'],
  logoutUrls: ['http://localhost:3000/', 'https://localhost:3000/'],
});

new KeycloakStack(app, 'MemoruKeycloakDev', {
  environment: 'dev',
  domainName: 'keycloak-dev.example.com', // TODO: Replace with actual domain
  // certificateArn: not required for dev
  // hostedZoneId: not required for dev
});

new LiffHostingStack(app, 'MemoruLiffHostingDev', {
  environment: 'dev',
  // domainName: optional for dev (uses CloudFront domain)
});

// ============================================================
// prod 環境
// ============================================================
new CognitoStack(app, 'MemoruCognitoProd', {
  environment: 'prod',
  cognitoDomainPrefix: 'memoru-prod', // TODO: Replace with actual domain prefix
  callbackUrls: ['https://liff.example.com/callback'], // TODO: Replace with actual URLs
  logoutUrls: ['https://liff.example.com/'], // TODO: Replace with actual URLs
});

new KeycloakStack(app, 'MemoruKeycloakProd', {
  environment: 'prod',
  domainName: 'keycloak.example.com', // TODO: Replace with actual domain
  certificateArn: 'arn:aws:acm:ap-northeast-1:123456789012:certificate/placeholder', // TODO: Replace with actual certificate ARN
  hostedZoneId: 'Z0123456789ABCDEF', // TODO: Replace with actual hosted zone ID
});

new LiffHostingStack(app, 'MemoruLiffHostingProd', {
  environment: 'prod',
  domainName: 'liff.example.com', // TODO: Replace with actual domain
  certificateArn: 'arn:aws:acm:us-east-1:123456789012:certificate/placeholder', // TODO: Replace with actual certificate ARN (must be us-east-1)
  hostedZoneId: 'Z0123456789ABCDEF', // TODO: Replace with actual hosted zone ID
});

app.synth();
