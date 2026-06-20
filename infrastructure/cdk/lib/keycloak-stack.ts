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
  hostedZoneName?: string;
  certificateArn?: string;
  hostedZoneId?: string;
  vpcCidr?: string;
  keycloakImage?: string;
  keycloakAdminUser?: string;
  dbInstanceClass?: ec2.InstanceType;
  dbAllocatedStorage?: number;
  /**
   * H-1: 指定すると Keycloak ALB の受信を当該 CIDR のみに制限する（既定は全公開）。
   * dev の Keycloak（IdP）は平文 HTTP かつ公開サブネット直結のため、運用者の固定 IP /
   * 社内 CIDR に絞れるよう env (MEMORU_DEV_KEYCLOAK_ALLOWED_CIDR) から注入できる。
   * 未指定時は従来どおり 0.0.0.0/0 を許可する（後方互換）。
   */
  albIngressCidr?: string;
}

export class KeycloakStack extends cdk.Stack {
  public readonly vpc: ec2.Vpc;
  public readonly dbInstance: rds.DatabaseInstance;

  constructor(scope: Construct, id: string, props: KeycloakStackProps) {
    super(scope, id, props);

    const isProd = props.environment === 'prod';
    // H-1: ALB ingress CIDR が指定された場合のみ受信を制限する（openListener を無効化して手動付与）。
    const restrictAlbIngress = !!props.albIngressCidr;

    // M-40: dev は証明書なし=平文 HTTP かつ ALB が public サブネット直結のため、
    // CIDR 制限なしだと Keycloak 管理コンソール / OIDC エンドポイントが平文 HTTP で
    // 0.0.0.0/0 に公開される。デフォルトを安全側に倒すと既存運用が壊れるため後方互換は
    // 維持しつつ、CIDR 未指定時は synth 時に警告して気づけるようにする。
    if (!isProd && !restrictAlbIngress) {
      cdk.Annotations.of(this).addWarning(
        'M-40: dev Keycloak ALB が 0.0.0.0/0 に平文 HTTP で公開されます。'
          + ' MEMORU_DEV_KEYCLOAK_ALLOWED_CIDR を設定して受信元 CIDR を制限してください。',
      );
    }
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
      // M-42: dev は DESTROY にして cdk destroy 時に同名シークレットが残らないように
      // する（残ると次回 deploy で「既に存在」エラーになり再構築が失敗する）。
      // prod は誤削除防止のため RETAIN。
      removalPolicy: isProd ? cdk.RemovalPolicy.RETAIN : cdk.RemovalPolicy.DESTROY,
    });

    const keycloakAdminSecret = new secretsmanager.Secret(this, 'KeycloakAdminSecret', {
      secretName: `memoru-${props.environment}-keycloak-admin-secret`,
      description: 'Keycloak admin credentials',
      generateSecretString: {
        secretStringTemplate: JSON.stringify({ username: keycloakAdminUser }),
        generateStringKey: 'password',
        // M-39: IdP 管理者は DB 認証情報より高権限のため、dbSecret と同じ 32 文字に
        // 統一する（excludeCharacters も揃える）。
        passwordLength: 32,
        excludeCharacters: '"@/\\',
      },
      // M-42: dev は DESTROY（同名シークレット残留による再デプロイ失敗を防ぐ）、prod は RETAIN。
      removalPolicy: isProd ? cdk.RemovalPolicy.RETAIN : cdk.RemovalPolicy.DESTROY,
    });

    // ============================================================
    // RDS PostgreSQL 17 (CDK/RDS で VER_18 は未提供のため VER_17 を使用)
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
      containerInsightsV2: isProd ? ecs.ContainerInsights.ENABLED : ecs.ContainerInsights.DISABLED,
    });

    // ============================================================
    // Log Group
    // ============================================================
    const logGroup = new logs.LogGroup(this, 'LogGroup', {
      logGroupName: `/ecs/memoru-${props.environment}-keycloak`,
      retention: isProd ? logs.RetentionDays.THREE_MONTHS : logs.RetentionDays.TWO_WEEKS,
      removalPolicy: isProd ? cdk.RemovalPolicy.RETAIN : cdk.RemovalPolicy.DESTROY,
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
        // H-1: CIDR 制限する場合は自動の 0.0.0.0/0 ingress を抑止し、下で明示付与する。
        openListener: !restrictAlbIngress,
        // Task image options
        taskImageOptions: {
          image: ecs.ContainerImage.fromRegistry(keycloakImage),
          containerPort: 8080,
          command: ['start', '--optimized'],
          environment: {
            KC_DB: 'postgres',
            KC_DB_URL: `jdbc:postgresql://${this.dbInstance.instanceEndpoint.hostname}:5432/keycloak`,
            KC_HOSTNAME: certificate ? props.domainName : '',
            KC_HOSTNAME_STRICT: isProd ? 'true' : 'false',
            KC_HOSTNAME_STRICT_HTTPS: isProd ? 'true' : 'false',
            KC_PROXY_HEADERS: 'xforwarded',
            // CR-1: prod でも HTTP(8080) を有効にする。
            // ApplicationLoadBalancedFargateService は targetProtocol 未指定時、
            // ターゲットグループ（ALB→コンテナ間）を HTTP に既定し、ヘルスチェックも
            // HTTP:8080 の /health/ready を叩く。prod で KC_HTTP_ENABLED='false' に
            // すると 8080 が無効化され、ALB ヘルスチェックが connection refused で
            // 永続失敗 → circuitBreaker でロールバックし Keycloak が起動しなくなる。
            // ALB が HTTPS(443) を終端し X-Forwarded-Proto: https を付与するため、
            // KC_PROXY_HEADERS=xforwarded と組み合わせれば内部 HTTP でも外部からは
            // HTTPS として扱われる。8080 は VPC 内（ALB→コンテナ）のみで外部非公開。
            KC_HTTP_ENABLED: 'true',
            KC_HTTP_PORT: '8080',
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

    // H-1: ingress CIDR 制限が指定された場合、ALB のリスナーポートを当該 CIDR のみに許可する。
    // openListener:false で両 listener の自動 ingress を抑止しているため、存在する全 listener
    // ポートを明示許可する必要がある。証明書ありの場合は HTTPS(443) に加えて redirectHTTP が
    // 生成する HTTP(80) リダイレクト listener も許可しないと、許可 CIDR からの HTTP→HTTPS
    // リダイレクトがタイムアウトする。証明書なし(dev)は HTTP(80) のみ。
    if (restrictAlbIngress) {
      const peer = ec2.Peer.ipv4(props.albIngressCidr!);
      if (certificate) {
        service.loadBalancer.connections.allowFrom(
          peer,
          ec2.Port.tcp(443),
          'Restricted Keycloak ALB ingress - HTTPS (MEMORU_DEV_KEYCLOAK_ALLOWED_CIDR)',
        );
        service.loadBalancer.connections.allowFrom(
          peer,
          ec2.Port.tcp(80),
          'Restricted Keycloak ALB ingress - HTTP redirect (MEMORU_DEV_KEYCLOAK_ALLOWED_CIDR)',
        );
      } else {
        service.loadBalancer.connections.allowFrom(
          peer,
          ec2.Port.tcp(80),
          'Restricted Keycloak ALB ingress - HTTP (MEMORU_DEV_KEYCLOAK_ALLOWED_CIDR)',
        );
      }
    }

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
      // M-43: zoneName に domainName（サブドメイン）をフォールバックすると、実際の
      // Hosted Zone（例: example.com）と不一致になり deploy 時に Route53 API が
      // エラーを返しうる。hostedZoneName は明示必須とし、未指定なら早期に失敗させる。
      if (!props.hostedZoneName) {
        throw new Error(
          'hostedZoneName is required when domainName and hostedZoneId are specified '
            + '(zoneName must point to the apex zone, e.g. example.com, not the record subdomain)',
        );
      }
      const zone = route53.HostedZone.fromHostedZoneAttributes(this, 'Zone', {
        hostedZoneId: props.hostedZoneId,
        zoneName: props.hostedZoneName,
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
