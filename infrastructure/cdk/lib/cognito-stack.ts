import * as cdk from 'aws-cdk-lib';
import * as cognito from 'aws-cdk-lib/aws-cognito';
import type { Construct } from 'constructs';

type Environment = 'dev' | 'staging' | 'prod';

export interface CognitoStackProps extends cdk.StackProps {
  environment: Environment;
  cognitoDomainPrefix: string;
  callbackUrls: string[];
  logoutUrls: string[];
  /** LINE Login Channel ID（両方指定時のみ LINE IdP を登録） */
  lineLoginChannelId?: string;
  /** LINE Login Channel Secret */
  lineLoginChannelSecret?: string;
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
    this.userPool.addDomain('UserPoolDomain', {
      cognitoDomain: {
        domainPrefix: props.cognitoDomainPrefix,
      },
    });

    // LINE Login 外部 OIDC IdP（両方の Props が指定された場合のみ作成）
    let lineProvider: cognito.UserPoolIdentityProviderOidc | undefined;
    if (props.lineLoginChannelId && props.lineLoginChannelSecret) {
      // LINE OIDC エンドポイントは .well-known/openid-configuration から取得可能だが、
      // CDK の UserPoolIdentityProviderOidc は手動指定が必要
      // ref: https://access.line.me/.well-known/openid-configuration
      lineProvider = new cognito.UserPoolIdentityProviderOidc(this, 'LineLoginProvider', {
        userPool: this.userPool,
        name: 'LINE',
        clientId: props.lineLoginChannelId,
        clientSecret: props.lineLoginChannelSecret,
        issuerUrl: 'https://access.line.me',
        scopes: ['openid', 'profile'],
        endpoints: {
          authorization: 'https://access.line.me/oauth2/v2.1/authorize',
          token: 'https://api.line.me/oauth2/v2.1/token',
          userInfo: 'https://api.line.me/oauth2/v2.1/userinfo',
          jwksUri: 'https://api.line.me/oauth2/v2.1/certs',
        },
        attributeMapping: {
          // Cognito は federated user の username を自動で LINE_<sub> に設定するため、
          // username マッピングは不要。name と picture のみマッピングする。
          custom: {
            name: cognito.ProviderAttribute.other('name'),
            picture: cognito.ProviderAttribute.other('picture'),
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
        cognito.UserPoolClientIdentityProvider.COGNITO,
        ...(lineProvider ? [cognito.UserPoolClientIdentityProvider.custom('LINE')] : []),
      ],
      accessTokenValidity: cdk.Duration.hours(1),
      idTokenValidity: cdk.Duration.hours(1),
      refreshTokenValidity: cdk.Duration.days(30),
      preventUserExistenceErrors: true,
    });

    // UserPoolClient が LINE IdP より先に作成されると CloudFormation エラーになるため明示的に依存を追加
    if (lineProvider) {
      this.userPoolClient.node.addDependency(lineProvider);
    }

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
