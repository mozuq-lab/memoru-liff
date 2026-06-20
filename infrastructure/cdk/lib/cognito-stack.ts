import * as cdk from 'aws-cdk-lib';
import * as cognito from 'aws-cdk-lib/aws-cognito';
import * as secretsmanager from 'aws-cdk-lib/aws-secretsmanager';
import type { Construct } from 'constructs';

type Environment = 'dev' | 'staging' | 'prod';

export interface CognitoStackProps extends cdk.StackProps {
  environment: Environment;
  cognitoDomainPrefix: string;
  callbackUrls: string[];
  logoutUrls: string[];
  /** LINE Login Channel ID（両方指定時のみ LINE IdP を登録） */
  lineLoginChannelId?: string;
  /**
   * LINE Login Channel Secret を保持する Secrets Manager シークレットの名前または ARN。
   * 指定すると CFN dynamic reference (`{{resolve:secretsmanager:...}}`) を使って
   * client_secret に埋め込むため、テンプレートや cdk.out に平文が残らない。
   *
   * シークレット本体（プレーンテキスト）はデプロイ前に手動で投入しておく必要がある。
   */
  lineLoginChannelSecretName?: string;
  /**
   * @deprecated 平文の Channel Secret を直接渡すと CloudFormation テンプレートと
   * cdk.out に Secret が残る。`lineLoginChannelSecretName` 経由の Secrets Manager
   * 参照を使うこと。後方互換のため残しているが、prod では使用禁止。
   */
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

    // LINE Login Channel Secret の解決:
    //   1. lineLoginChannelSecretName が指定されていれば Secrets Manager の dynamic
    //      reference に解決する (CFN テンプレートに平文が残らない)
    //   2. lineLoginChannelSecret (deprecated) が指定されていれば文字列をそのまま使う
    //      ※ prod 環境ではフォールバック自体を禁止する
    let resolvedLineSecret: string | undefined;
    if (props.lineLoginChannelSecretName) {
      const lineSecret = secretsmanager.Secret.fromSecretNameV2(
        this,
        'LineLoginChannelSecret',
        props.lineLoginChannelSecretName,
      );
      // UserPoolIdentityProviderOidc.clientSecret は string 型を要求するため
      // unsafeUnwrap で Token を文字列化するが、CFN レベルでは dynamic reference
      // (`{{resolve:secretsmanager:...}}`) として解決される。
      resolvedLineSecret = lineSecret.secretValue.unsafeUnwrap();
    } else if (props.lineLoginChannelSecret) {
      if (props.environment === 'prod') {
        throw new Error(
          'LINE Channel Secret は prod では Secrets Manager 経由 (lineLoginChannelSecretName) で渡してください。'
            + ' 平文プロパティ (lineLoginChannelSecret) は prod では使用禁止です。',
        );
      }
      resolvedLineSecret = props.lineLoginChannelSecret;
    }

    // LINE Login 外部 OIDC IdP（Channel ID と Secret が両方解決できた場合のみ作成）
    let lineProvider: cognito.UserPoolIdentityProviderOidc | undefined;
    if (props.lineLoginChannelId && resolvedLineSecret) {
      // LINE OIDC エンドポイントは .well-known/openid-configuration から取得可能だが、
      // CDK の UserPoolIdentityProviderOidc は手動指定が必要
      // ref: https://access.line.me/.well-known/openid-configuration
      lineProvider = new cognito.UserPoolIdentityProviderOidc(this, 'LineLoginProvider', {
        userPool: this.userPool,
        name: 'LINE',
        clientId: props.lineLoginChannelId,
        clientSecret: resolvedLineSecret,
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
      // L-33: トークン失効（侵害されたリフレッシュトークンの即時無効化）を明示的に有効化。
      // CDK のデフォルトは true だが、デフォルト変更時に意図せず無効化されないよう宣言する。
      enableTokenRevocation: true,
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
