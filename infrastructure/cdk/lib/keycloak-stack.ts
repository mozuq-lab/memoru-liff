import * as cdk from 'aws-cdk-lib';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as ecs from 'aws-cdk-lib/aws-ecs';
import * as ecs_patterns from 'aws-cdk-lib/aws-ecs-patterns';
import * as rds from 'aws-cdk-lib/aws-rds';
import * as secretsmanager from 'aws-cdk-lib/aws-secretsmanager';
import * as acm from 'aws-cdk-lib/aws-certificatemanager';
import * as elbv2 from 'aws-cdk-lib/aws-elasticloadbalancingv2';
import * as route53 from 'aws-cdk-lib/aws-route53';
import * as targets from 'aws-cdk-lib/aws-route53-targets';
import * as logs from 'aws-cdk-lib/aws-logs';
import type { Construct } from 'constructs';

type Environment = 'dev' | 'staging' | 'prod';

export interface KeycloakStackProps extends cdk.StackProps {
  environment: Environment;
  domainName: string;
  certificateArn?: string;
  hostedZoneId?: string;
  vpcCidr?: string;
  keycloakImage?: string;
  keycloakAdminUser?: string;
  dbInstanceClass?: ec2.InstanceType;
  dbAllocatedStorage?: number;
}

export class KeycloakStack extends cdk.Stack {
  public readonly vpc: ec2.Vpc;
  public readonly dbInstance: rds.DatabaseInstance;

  constructor(scope: Construct, id: string, props: KeycloakStackProps) {
    super(scope, id, props);

    const isProd = props.environment === 'prod';
    const keycloakImage = props.keycloakImage ?? 'quay.io/keycloak/keycloak:24.0';
    const keycloakAdminUser = props.keycloakAdminUser ?? 'admin';
    const dbAllocatedStorage = props.dbAllocatedStorage ?? 20;

    // Validate: prod requires certificate
    if (isProd && !props.certificateArn) {
      throw new Error('CertificateArn is required for prod environment');
    }

    // ============================================================
    // VPC and Networking
    // ============================================================
    this.vpc = new ec2.Vpc(this, 'Vpc', {
      vpcName: `memoru-${props.environment}-vpc`,
      ipAddresses: ec2.IpAddresses.cidr(props.vpcCidr ?? '10.0.0.0/16'),
      maxAzs: 2,
      natGateways: isProd ? 1 : 0,
      subnetConfiguration: [
        {
          cidrMask: 24,
          name: 'Public',
          subnetType: ec2.SubnetType.PUBLIC,
        },
        {
          cidrMask: 24,
          name: 'Private',
          subnetType: isProd
            ? ec2.SubnetType.PRIVATE_WITH_EGRESS
            : ec2.SubnetType.PRIVATE_ISOLATED,
        },
      ],
    });

    // ============================================================
    // Secrets Manager
    // ============================================================
    const dbSecret = new secretsmanager.Secret(this, 'DBSecret', {
      secretName: `memoru-${props.environment}-keycloak-db-secret`,
      description: 'Keycloak database credentials',
      generateSecretString: {
        secretStringTemplate: JSON.stringify({ username: 'keycloak' }),
        generateStringKey: 'password',
        passwordLength: 32,
        excludeCharacters: '"@/\\',
      },
    });

    const keycloakAdminSecret = new secretsmanager.Secret(this, 'KeycloakAdminSecret', {
      secretName: `memoru-${props.environment}-keycloak-admin-secret`,
      description: 'Keycloak admin credentials',
      generateSecretString: {
        secretStringTemplate: JSON.stringify({ username: keycloakAdminUser }),
        generateStringKey: 'password',
        passwordLength: 16,
        excludeCharacters: '"@/\\',
      },
    });

    // ============================================================
    // RDS PostgreSQL 18
    // ============================================================
    const dbSecurityGroup = new ec2.SecurityGroup(this, 'RDSSecurityGroup', {
      vpc: this.vpc,
      securityGroupName: `memoru-${props.environment}-keycloak-rds-sg`,
      description: 'Security group for Keycloak RDS',
    });

    this.dbInstance = new rds.DatabaseInstance(this, 'Database', {
      instanceIdentifier: `memoru-${props.environment}-keycloak-db`,
      engine: rds.DatabaseInstanceEngine.postgres({
        version: rds.PostgresEngineVersion.VER_17,
      }),
      instanceType: props.dbInstanceClass ?? ec2.InstanceType.of(
        ec2.InstanceClass.T3,
        ec2.InstanceSize.MICRO,
      ),
      vpc: this.vpc,
      vpcSubnets: { subnetType: isProd ? ec2.SubnetType.PRIVATE_WITH_EGRESS : ec2.SubnetType.PRIVATE_ISOLATED },
      securityGroups: [dbSecurityGroup],
      databaseName: 'keycloak',
      credentials: rds.Credentials.fromSecret(dbSecret),
      allocatedStorage: dbAllocatedStorage,
      storageType: rds.StorageType.GP3,
      storageEncrypted: true,
      multiAz: isProd,
      deletionProtection: isProd,
      removalPolicy: isProd ? cdk.RemovalPolicy.SNAPSHOT : cdk.RemovalPolicy.DESTROY,
      backupRetention: cdk.Duration.days(7),
      publiclyAccessible: false,
      parameters: {
        client_encoding: 'UTF8',
      },
    });

    // ============================================================
    // ECS Cluster
    // ============================================================
    const cluster = new ecs.Cluster(this, 'Cluster', {
      clusterName: `memoru-${props.environment}-keycloak-cluster`,
      vpc: this.vpc,
      containerInsights: isProd,
    });

    // ============================================================
    // Log Group
    // ============================================================
    const logGroup = new logs.LogGroup(this, 'LogGroup', {
      logGroupName: `/ecs/memoru-${props.environment}-keycloak`,
      retention: isProd ? logs.RetentionDays.THREE_MONTHS : logs.RetentionDays.TWO_WEEKS,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    // ============================================================
    // Certificate (optional)
    // ============================================================
    const certificate = props.certificateArn
      ? acm.Certificate.fromCertificateArn(this, 'Cert', props.certificateArn)
      : undefined;

    // ============================================================
    // ApplicationLoadBalancedFargateService
    // ============================================================
    const service = new ecs_patterns.ApplicationLoadBalancedFargateService(
      this, 'KeycloakService', {
        cluster,
        serviceName: `memoru-${props.environment}-keycloak-service`,
        cpu: 512,
        memoryLimitMiB: 1024,
        desiredCount: 1,
        // Place tasks in public subnets for dev (no NAT), private for prod
        taskSubnets: {
          subnetType: isProd
            ? ec2.SubnetType.PRIVATE_WITH_EGRESS
            : ec2.SubnetType.PUBLIC,
        },
        assignPublicIp: !isProd,
        // HTTPS settings
        certificate,
        protocol: certificate
          ? elbv2.ApplicationProtocol.HTTPS
          : elbv2.ApplicationProtocol.HTTP,
        redirectHTTP: !!certificate,
        // Task image options
        taskImageOptions: {
          image: ecs.ContainerImage.fromRegistry(keycloakImage),
          containerPort: 8080,
          command: ['start', '--optimized'],
          environment: {
            KC_DB: 'postgres',
            KC_DB_URL: `jdbc:postgresql://${this.dbInstance.instanceEndpoint.hostname}:5432/keycloak`,
            KC_HOSTNAME: props.domainName,
            KC_HOSTNAME_STRICT: isProd ? 'true' : 'false',
            KC_HOSTNAME_STRICT_HTTPS: isProd ? 'true' : 'false',
            KC_PROXY_HEADERS: 'xforwarded',
            KC_HTTP_ENABLED: isProd ? 'false' : 'true',
            KC_HEALTH_ENABLED: 'true',
            KC_METRICS_ENABLED: 'true',
          },
          secrets: {
            KC_DB_USERNAME: ecs.Secret.fromSecretsManager(dbSecret, 'username'),
            KC_DB_PASSWORD: ecs.Secret.fromSecretsManager(dbSecret, 'password'),
            KEYCLOAK_ADMIN: ecs.Secret.fromSecretsManager(keycloakAdminSecret, 'username'),
            KEYCLOAK_ADMIN_PASSWORD: ecs.Secret.fromSecretsManager(keycloakAdminSecret, 'password'),
          },
          logDriver: ecs.LogDrivers.awsLogs({
            logGroup,
            streamPrefix: 'keycloak',
          }),
        },
        circuitBreaker: { rollback: true },
        healthCheckGracePeriod: cdk.Duration.seconds(180),
      },
    );

    // Configure ALB target group health check
    service.targetGroup.configureHealthCheck({
      path: '/health/ready',
      healthyHttpCodes: '200',
    });

    // Allow ECS tasks to connect to RDS
    dbSecurityGroup.addIngressRule(
      service.service.connections.securityGroups[0],
      ec2.Port.tcp(5432),
      'PostgreSQL from ECS',
    );

    // ============================================================
    // Route53 DNS Record (Optional)
    // ============================================================
    if (props.domainName && props.hostedZoneId) {
      const zone = route53.HostedZone.fromHostedZoneAttributes(this, 'Zone', {
        hostedZoneId: props.hostedZoneId,
        zoneName: props.domainName,
      });
      new route53.ARecord(this, 'DNSRecord', {
        zone,
        recordName: props.domainName,
        target: route53.RecordTarget.fromAlias(
          new targets.LoadBalancerTarget(service.loadBalancer),
        ),
      });
    }

    // ============================================================
    // Outputs
    // ============================================================
    new cdk.CfnOutput(this, 'VpcId', {
      value: this.vpc.vpcId,
      exportName: `memoru-${props.environment}-vpc-id`,
      description: 'VPC ID',
    });

    const keycloakUrl = certificate
      ? `https://${props.domainName}`
      : `http://${service.loadBalancer.loadBalancerDnsName}`;
    new cdk.CfnOutput(this, 'KeycloakURL', {
      value: keycloakUrl,
      description: 'Keycloak URL',
    });

    new cdk.CfnOutput(this, 'ALBDNSName', {
      value: service.loadBalancer.loadBalancerDnsName,
      exportName: `memoru-${props.environment}-keycloak-alb-dns`,
      description: 'ALB DNS Name',
    });

    new cdk.CfnOutput(this, 'RDSEndpoint', {
      value: this.dbInstance.instanceEndpoint.hostname,
      exportName: `memoru-${props.environment}-keycloak-db-endpoint`,
      description: 'RDS Endpoint',
    });

    new cdk.CfnOutput(this, 'ECSClusterArn', {
      value: cluster.clusterArn,
      exportName: `memoru-${props.environment}-keycloak-cluster-arn`,
      description: 'ECS Cluster ARN',
    });

    new cdk.CfnOutput(this, 'DBSecretArn', {
      value: dbSecret.secretArn,
      exportName: `memoru-${props.environment}-keycloak-db-secret-arn`,
      description: 'Database Secret ARN',
    });

    new cdk.CfnOutput(this, 'KeycloakAdminSecretArn', {
      value: keycloakAdminSecret.secretArn,
      exportName: `memoru-${props.environment}-keycloak-admin-secret-arn`,
      description: 'Keycloak Admin Secret ARN',
    });
  }
}
