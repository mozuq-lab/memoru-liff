import * as cdk from 'aws-cdk-lib';
import { Template, Match } from 'aws-cdk-lib/assertions';
import { KeycloakStack, type KeycloakStackProps } from '../lib/keycloak-stack';

const devProps: KeycloakStackProps = {
  environment: 'dev',
  domainName: 'keycloak-dev.example.com',
};

const prodProps: KeycloakStackProps = {
  environment: 'prod',
  domainName: 'keycloak.example.com',
  hostedZoneName: 'example.com',
  certificateArn: 'arn:aws:acm:ap-northeast-1:123456789012:certificate/test-cert',
  hostedZoneId: 'Z0123456789ABCDEF',
};

function createStack(props: KeycloakStackProps): KeycloakStack {
  const app = new cdk.App();
  return new KeycloakStack(app, 'TestKeycloakStack', props);
}

describe('KeycloakStack', () => {
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

  describe('Validation', () => {
    test('prod without certificateArn throws error', () => {
      expect(() => createStack({
        environment: 'prod',
        domainName: 'keycloak.example.com',
      })).toThrow('CertificateArn is required for prod environment');
    });
  });

  describe('Environment differences', () => {
    test('dev: no NAT Gateway', () => {
      const template = Template.fromStack(createStack(devProps));
      template.resourceCountIs('AWS::EC2::NatGateway', 0);
    });

    test('prod: 1 NAT Gateway', () => {
      const template = Template.fromStack(createStack(prodProps));
      template.resourceCountIs('AWS::EC2::NatGateway', 1);
    });

    test('dev: RDS MultiAZ is false', () => {
      const template = Template.fromStack(createStack(devProps));
      template.hasResourceProperties('AWS::RDS::DBInstance', {
        MultiAZ: false,
      });
    });

    test('prod: RDS MultiAZ is true', () => {
      const template = Template.fromStack(createStack(prodProps));
      template.hasResourceProperties('AWS::RDS::DBInstance', {
        MultiAZ: true,
      });
    });

    test('dev: RDS DeletionProtection is false', () => {
      const template = Template.fromStack(createStack(devProps));
      template.hasResourceProperties('AWS::RDS::DBInstance', {
        DeletionProtection: false,
      });
    });

    test('prod: RDS DeletionProtection is true', () => {
      const template = Template.fromStack(createStack(prodProps));
      template.hasResourceProperties('AWS::RDS::DBInstance', {
        DeletionProtection: true,
      });
    });

    test('dev: ECS AssignPublicIp is ENABLED', () => {
      const template = Template.fromStack(createStack(devProps));
      template.hasResourceProperties('AWS::ECS::Service', {
        NetworkConfiguration: {
          AwsvpcConfiguration: {
            AssignPublicIp: 'ENABLED',
          },
        },
      });
    });

    test('prod: ECS AssignPublicIp is DISABLED', () => {
      const template = Template.fromStack(createStack(prodProps));
      template.hasResourceProperties('AWS::ECS::Service', {
        NetworkConfiguration: {
          AwsvpcConfiguration: {
            AssignPublicIp: 'DISABLED',
          },
        },
      });
    });

    test('dev: LogGroup RemovalPolicy is DESTROY', () => {
      const template = Template.fromStack(createStack(devProps));
      template.hasResource('AWS::Logs::LogGroup', {
        UpdateReplacePolicy: 'Delete',
        DeletionPolicy: 'Delete',
      });
    });

    test('prod: LogGroup RemovalPolicy is RETAIN', () => {
      const template = Template.fromStack(createStack(prodProps));
      template.hasResource('AWS::Logs::LogGroup', {
        UpdateReplacePolicy: 'Retain',
        DeletionPolicy: 'Retain',
      });
    });
  });

  describe('Security', () => {
    test('RDS StorageEncrypted is true', () => {
      const template = Template.fromStack(createStack(devProps));
      template.hasResourceProperties('AWS::RDS::DBInstance', {
        StorageEncrypted: true,
      });
    });

    test('RDS PubliclyAccessible is false', () => {
      const template = Template.fromStack(createStack(devProps));
      template.hasResourceProperties('AWS::RDS::DBInstance', {
        PubliclyAccessible: false,
      });
    });
  });
});
