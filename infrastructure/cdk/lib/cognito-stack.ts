import * as cdk from 'aws-cdk-lib';
import * as cognito from 'aws-cdk-lib/aws-cognito';
import type { Construct } from 'constructs';

type Environment = 'dev' | 'staging' | 'prod';

export interface CognitoStackProps extends cdk.StackProps {
  environment: Environment;
  cognitoDomainPrefix: string;
  callbackUrls: string[];
  logoutUrls: string[];
  // 【LINE Login 追加 Props】: LINE Login 外部 OIDC IdP 登録用のオプショナルプロパティ 🔵
  // 【設計方針】: 両方が指定された場合のみ LINE IdP を登録し、後方互換性を維持 (REQ-006)
  lineLoginChannelId?: string;     // LINE Login Channel ID（省略時は LINE IdP 未登録）
  lineLoginChannelSecret?: string; // LINE Login Channel Secret
}

export class CognitoStack extends cdk.Stack {
  public readonly userPool: cognito.UserPool;
  public readonly userPoolClient: cognito.UserPoolClient;

  constructor(scope: Construct, id: string, props: CognitoStackProps) {
    super(scope, id, props);

    const isProd = props.environment === 'prod';

    // ============================================================
    // Cognito User Pool
    // ============================================================
    this.userPool = new cognito.UserPool(this, 'UserPool', {
      userPoolName: `memoru-${props.environment}-user-pool`,
      selfSignUpEnabled: true,
      signInAliases: { email: true },
      signInCaseSensitive: false,
      autoVerify: { email: true },
      // MFA configuration (OPTIONAL: users can enable TOTP)
      mfa: cognito.Mfa.OPTIONAL,
      mfaSecondFactor: { sms: false, otp: true },
      // Password policy
      passwordPolicy: {
        minLength: 8,
        requireLowercase: true,
        requireUppercase: true,
        requireDigits: true,
        requireSymbols: true,
        tempPasswordValidity: cdk.Duration.days(7),
      },
      accountRecovery: cognito.AccountRecovery.EMAIL_ONLY,
      deletionProtection: isProd,
      removalPolicy: isProd ? cdk.RemovalPolicy.RETAIN : cdk.RemovalPolicy.DESTROY,
    });

    // ============================================================
    // Cognito User Pool Domain (Prefix-based)
    // ============================================================
    const domain = this.userPool.addDomain('UserPoolDomain', {
      cognitoDomain: {
        domainPrefix: props.cognitoDomainPrefix,
      },
    });

    // ============================================================
    // LINE Login 外部 OIDC IdP（条件付き作成）
    // ============================================================
    // 【機能概要】: LINE Login を外部 OIDC IdP として Cognito UserPool に登録する 🔵
    // 【実装方針】: lineLoginChannelId と lineLoginChannelSecret の両方が指定された場合のみ作成 (REQ-001)
    // 【後方互換性】: Props 未指定時は既存動作（COGNITO のみ）を維持する (REQ-401)
    // 【変数宣言位置】: UserPoolClient の supportedIdentityProviders で参照するため、
    //   addClient 呼び出し前に lineProvider を定義する必要がある
    let lineProvider: cognito.UserPoolIdentityProviderOidc | undefined;
    if (props.lineLoginChannelId && props.lineLoginChannelSecret) {
      // 【LINE IdP 作成】: LINE Login の OIDC エンドポイントを手動指定して登録 (REQ-002) 🔵
      // 【エンドポイント手動指定】: LINE は .well-known/openid-configuration に非対応のため、各エンドポイントを明示
      lineProvider = new cognito.UserPoolIdentityProviderOidc(this, 'LineLoginProvider', {
        userPool: this.userPool,
        name: 'LINE', // 【プロバイダ名】: Cognito Hosted UI の LINE ログインボタン識別子
        clientId: props.lineLoginChannelId,
        clientSecret: props.lineLoginChannelSecret,
        issuerUrl: 'https://access.line.me', // 🟡 LINE OIDC Issuer URL
        scopes: ['openid', 'profile'], // 【スコープ】: LINE ユーザー属性取得に必要な最小スコープ
        endpoints: {
          // 【LINE OIDC エンドポイント手動指定】: 各エンドポイントを手動設定 (REQ-002) 🟡
          authorization: 'https://access.line.me/oauth2/v2.1/authorize',
          token: 'https://api.line.me/oauth2/v2.1/token',
          userInfo: 'https://api.line.me/v2/profile',
          jwksUri: 'https://api.line.me/oauth2/v2.1/certs',
        },
        attributeMapping: {
          // 【属性マッピング】: LINE 属性を Cognito ユーザー属性にマッピング (REQ-003) 🔵
          // 【custom 使用】: 標準マッピングキーでは username が undefined になるため custom を使用
          custom: {
            username: cognito.ProviderAttribute.other('sub'),     // LINE ユーザー ID → Cognito username
            name: cognito.ProviderAttribute.other('name'),        // LINE 表示名 → Cognito name
            picture: cognito.ProviderAttribute.other('picture'),  // LINE プロフィール画像 → Cognito picture
          },
        },
      });
    }

    // ============================================================
    // Cognito User Pool Client (Public, PKCE)
    // ============================================================
    this.userPoolClient = this.userPool.addClient('LiffClient', {
      userPoolClientName: `memoru-${props.environment}-liff-client`,
      generateSecret: false, // Public client (SPA + PKCE)
      oAuth: {
        flows: { authorizationCodeGrant: true },
        scopes: [
          cognito.OAuthScope.OPENID,
          cognito.OAuthScope.PROFILE,
          cognito.OAuthScope.EMAIL,
        ],
        callbackUrls: props.callbackUrls,
        logoutUrls: props.logoutUrls,
      },
      authFlows: {
        custom: false,
        userSrp: false,
      },
      supportedIdentityProviders: [
        // 【supportedIdentityProviders】: LINE IdP が登録されている場合のみ追加 (REQ-004, REQ-005) 🔵
        // 【条件付き追加】: lineProvider が存在する場合のみ LINE を配列に追加
        cognito.UserPoolClientIdentityProvider.COGNITO,
        ...(lineProvider ? [cognito.UserPoolClientIdentityProvider.custom('LINE')] : []),
      ],
      accessTokenValidity: cdk.Duration.hours(1),
      idTokenValidity: cdk.Duration.hours(1),
      refreshTokenValidity: cdk.Duration.days(30),
      preventUserExistenceErrors: true,
    });

    // ============================================================
    // Outputs
    // ============================================================
    new cdk.CfnOutput(this, 'UserPoolId', {
      value: this.userPool.userPoolId,
      exportName: `memoru-${props.environment}-cognito-user-pool-id`,
      description: 'Cognito User Pool ID',
    });

    new cdk.CfnOutput(this, 'UserPoolArn', {
      value: this.userPool.userPoolArn,
      exportName: `memoru-${props.environment}-cognito-user-pool-arn`,
      description: 'Cognito User Pool ARN',
    });

    new cdk.CfnOutput(this, 'UserPoolClientId', {
      value: this.userPoolClient.userPoolClientId,
      exportName: `memoru-${props.environment}-cognito-client-id`,
      description: 'Cognito User Pool Client ID',
    });

    new cdk.CfnOutput(this, 'OidcIssuerUrl', {
      value: `https://cognito-idp.${this.region}.amazonaws.com/${this.userPool.userPoolId}`,
      exportName: `memoru-${props.environment}-cognito-oidc-issuer`,
      description: 'OIDC Issuer URL for backend configuration',
    });

    new cdk.CfnOutput(this, 'CognitoDomainUrl', {
      value: `https://${props.cognitoDomainPrefix}.auth.${this.region}.amazoncognito.com`,
      exportName: `memoru-${props.environment}-cognito-domain-url`,
      description: 'Cognito Hosted UI domain URL',
    });
  }
}
