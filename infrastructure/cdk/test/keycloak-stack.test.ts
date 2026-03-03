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

    test('dev: LogGroup retention is 14 days, RemovalPolicy is DESTROY', () => {
      const template = Template.fromStack(createStack(devProps));
      template.resourceCountIs('AWS::Logs::LogGroup', 1);
      template.hasResource('AWS::Logs::LogGroup', {
        Properties: {
          LogGroupName: '/ecs/memoru-dev-keycloak',
          RetentionInDays: 14,
        },
        UpdateReplacePolicy: 'Delete',
        DeletionPolicy: 'Delete',
      });
    });

    test('prod: LogGroup retention is 90 days, RemovalPolicy is RETAIN', () => {
      const template = Template.fromStack(createStack(prodProps));
      template.resourceCountIs('AWS::Logs::LogGroup', 1);
      template.hasResource('AWS::Logs::LogGroup', {
        Properties: {
          LogGroupName: '/ecs/memoru-prod-keycloak',
          RetentionInDays: 90,
        },
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

  describe('HTTPS and Load Balancer', () => {
    test('dev: Listener is HTTP on port 80', () => {
      const template = Template.fromStack(createStack(devProps));
      template.hasResourceProperties('AWS::ElasticLoadBalancingV2::Listener', {
        Port: 80,
        Protocol: 'HTTP',
      });
    });

    test('prod: Listener is HTTPS on port 443 with certificate', () => {
      const template = Template.fromStack(createStack(prodProps));
      template.hasResourceProperties('AWS::ElasticLoadBalancingV2::Listener', {
        Port: 443,
        Protocol: 'HTTPS',
        Certificates: [
          { CertificateArn: prodProps.certificateArn },
        ],
      });
    });

    test('prod: HTTP to HTTPS redirect listener exists', () => {
      const template = Template.fromStack(createStack(prodProps));
      template.hasResourceProperties('AWS::ElasticLoadBalancingV2::Listener', {
        Port: 80,
        DefaultActions: Match.arrayWith([
          Match.objectLike({
            Type: 'redirect',
            RedirectConfig: Match.objectLike({
              Protocol: 'HTTPS',
              Port: '443',
              StatusCode: 'HTTP_301',
            }),
          }),
        ]),
      });
    });

    test('dev: no HTTP redirect listener', () => {
      const template = Template.fromStack(createStack(devProps));
      // dev has only 1 listener (HTTP), no redirect
      template.resourceCountIs('AWS::ElasticLoadBalancingV2::Listener', 1);
    });

    test('prod: 2 listeners (HTTPS + HTTP redirect)', () => {
      const template = Template.fromStack(createStack(prodProps));
      template.resourceCountIs('AWS::ElasticLoadBalancingV2::Listener', 2);
    });
  });

  describe('Health check', () => {
    test('TargetGroup health check path is /health/ready', () => {
      const template = Template.fromStack(createStack(devProps));
      template.hasResourceProperties('AWS::ElasticLoadBalancingV2::TargetGroup', {
        HealthCheckPath: '/health/ready',
        Matcher: { HttpCode: '200' },
      });
    });
  });

  describe('DNS', () => {
    test('prod: Route53 A record is created', () => {
      const template = Template.fromStack(createStack(prodProps));
      template.hasResourceProperties('AWS::Route53::RecordSet', {
        Name: 'keycloak.example.com.',
        Type: 'A',
        HostedZoneId: 'Z0123456789ABCDEF',
      });
    });

    test('no Route53 record without hostedZoneId', () => {
      const template = Template.fromStack(createStack(devProps));
      template.resourceCountIs('AWS::Route53::RecordSet', 0);
    });
  });
});
