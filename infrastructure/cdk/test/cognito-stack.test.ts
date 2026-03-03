import * as cdk from 'aws-cdk-lib';
import { Template } from 'aws-cdk-lib/assertions';
import { CognitoStack, type CognitoStackProps } from '../lib/cognito-stack';

const devProps: CognitoStackProps = {
  environment: 'dev',
  cognitoDomainPrefix: 'memoru-dev-test',
  callbackUrls: ['http://localhost:3000/callback'],
  logoutUrls: ['http://localhost:3000/'],
};

const prodProps: CognitoStackProps = {
  environment: 'prod',
  cognitoDomainPrefix: 'memoru-prod-test',
  callbackUrls: ['https://app.example.com/callback'],
  logoutUrls: ['https://app.example.com/'],
};

function createStack(props: CognitoStackProps): CognitoStack {
  const app = new cdk.App();
  return new CognitoStack(app, 'TestCognitoStack', props);
}

describe('CognitoStack', () => {
  describe('Snapshot', () => {
    test('dev environment matches snapshot', () => {
      const template = Template.fromStack(createStack(devProps));
      expect(template.toJSON()).toMatchSnapshot();
    });

    test('prod environment matches snapshot', () => {
      const template = Template.fromStack(createStack(prodProps));
      expect(template.toJSON()).toMatchSnapshot();
    });
  });

  describe('Environment differences', () => {
    test('dev: DeletionProtection is INACTIVE', () => {
      const template = Template.fromStack(createStack(devProps));
      template.hasResourceProperties('AWS::Cognito::UserPool', {
        DeletionProtection: 'INACTIVE',
      });
    });

    test('prod: DeletionProtection is ACTIVE', () => {
      const template = Template.fromStack(createStack(prodProps));
      template.hasResourceProperties('AWS::Cognito::UserPool', {
        DeletionProtection: 'ACTIVE',
      });
    });

    test('dev: RemovalPolicy is DESTROY', () => {
      const template = Template.fromStack(createStack(devProps));
      template.hasResource('AWS::Cognito::UserPool', {
        UpdateReplacePolicy: 'Delete',
        DeletionPolicy: 'Delete',
      });
    });

    test('prod: RemovalPolicy is RETAIN', () => {
      const template = Template.fromStack(createStack(prodProps));
      template.hasResource('AWS::Cognito::UserPool', {
        UpdateReplacePolicy: 'Retain',
        DeletionPolicy: 'Retain',
      });
    });
  });

  describe('Security', () => {
    test('password policy meets requirements', () => {
      const template = Template.fromStack(createStack(devProps));
      template.hasResourceProperties('AWS::Cognito::UserPool', {
        Policies: {
          PasswordPolicy: {
            MinimumLength: 8,
            RequireLowercase: true,
            RequireUppercase: true,
            RequireNumbers: true,
            RequireSymbols: true,
          },
        },
      });
    });

    test('MFA is OPTIONAL with TOTP', () => {
      const template = Template.fromStack(createStack(devProps));
      template.hasResourceProperties('AWS::Cognito::UserPool', {
        MfaConfiguration: 'OPTIONAL',
        EnabledMfas: ['SOFTWARE_TOKEN_MFA'],
      });
    });
  });

  describe('OIDC', () => {
    test('OAuth flows and scopes are correctly configured', () => {
      const template = Template.fromStack(createStack(devProps));
      template.hasResourceProperties('AWS::Cognito::UserPoolClient', {
        AllowedOAuthFlows: ['code'],
        AllowedOAuthScopes: ['openid', 'profile', 'email'],
        AllowedOAuthFlowsUserPoolClient: true,
      });
    });

    test('CallbackURLs are set from props', () => {
      const template = Template.fromStack(createStack(devProps));
      template.hasResourceProperties('AWS::Cognito::UserPoolClient', {
        CallbackURLs: ['http://localhost:3000/callback'],
      });
    });

    test('LogoutURLs are set from props', () => {
      const template = Template.fromStack(createStack(devProps));
      template.hasResourceProperties('AWS::Cognito::UserPoolClient', {
        LogoutURLs: ['http://localhost:3000/'],
      });
    });

    test('prod: CallbackURLs and LogoutURLs use production URLs', () => {
      const template = Template.fromStack(createStack(prodProps));
      template.hasResourceProperties('AWS::Cognito::UserPoolClient', {
        CallbackURLs: ['https://app.example.com/callback'],
        LogoutURLs: ['https://app.example.com/'],
      });
    });

    test('token validity is configured correctly', () => {
      const template = Template.fromStack(createStack(devProps));
      template.hasResourceProperties('AWS::Cognito::UserPoolClient', {
        AccessTokenValidity: 60,
        IdTokenValidity: 60,
        RefreshTokenValidity: 43200,
        TokenValidityUnits: {
          AccessToken: 'minutes',
          IdToken: 'minutes',
          RefreshToken: 'minutes',
        },
      });
    });

    test('client is public (no secret)', () => {
      const template = Template.fromStack(createStack(devProps));
      template.hasResourceProperties('AWS::Cognito::UserPoolClient', {
        GenerateSecret: false,
      });
    });
  });

  describe('Domain', () => {
    test('UserPool domain prefix is set from props', () => {
      const template = Template.fromStack(createStack(devProps));
      template.hasResourceProperties('AWS::Cognito::UserPoolDomain', {
        Domain: 'memoru-dev-test',
      });
    });

    test('prod: UserPool domain prefix is set correctly', () => {
      const template = Template.fromStack(createStack(prodProps));
      template.hasResourceProperties('AWS::Cognito::UserPoolDomain', {
        Domain: 'memoru-prod-test',
      });
    });
  });
});
