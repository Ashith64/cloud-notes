"""
Stage 8B CloudFormation Template Validation Tests.
Verifies the application stack resources added to infra/stack.yaml:
- New parameters: BackupRetentionDays, MinCapacity, CpuTarget
- Updated resources: DBInstance, AppLogGroup, AppInstanceRole (SSM managed policy)
- New resources: SNS Topic & Subscription, Launch Template, ALB, Target Group, Listener,
  ASG, Scaling Policy, 4 CloudWatch Alarms, and CloudWatch Dashboard
- Required Outputs: LoadBalancerUrl, DashboardUrl, DbEndpoint
"""
import json
from pathlib import Path
import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
TEMPLATE_PATH = REPO_ROOT / "infra" / "stack.yaml"


class CFTag:
    """Wrapper to hold CloudFormation YAML short tags like !Ref and !GetAtt."""
    def __init__(self, tag, val):
        self.tag = tag
        self.val = val

    def __repr__(self):
        return f"{self.tag}({self.val})"


def _cfn_constructor(tag):
    def constructor(loader, node):
        if isinstance(node, yaml.ScalarNode):
            val = loader.construct_scalar(node)
        elif isinstance(node, yaml.SequenceNode):
            val = loader.construct_sequence(node)
        else:
            val = loader.construct_mapping(node)
        return CFTag(tag, val)
    return constructor


def load_cfn_template():
    for tag in [
        "!Ref", "!Sub", "!GetAtt", "!Join", "!Select",
        "!Split", "!FindInMap", "!Base64", "!GetAZs", "!ImportValue"
    ]:
        yaml.SafeLoader.add_constructor(tag, _cfn_constructor(tag))

    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="module")
def template():
    assert TEMPLATE_PATH.exists(), f"Missing template at {TEMPLATE_PATH}"
    return load_cfn_template()


def test_stage8b_parameters(template):
    params = template.get("Parameters", {})
    assert "BackupRetentionDays" in params
    assert params["BackupRetentionDays"]["Default"] == 7
    assert params["BackupRetentionDays"]["MinValue"] == 1
    assert params["BackupRetentionDays"]["MaxValue"] == 35

    assert "MinCapacity" in params
    assert params["MinCapacity"]["Default"] == 0

    assert "DesiredCapacity" in params
    assert params["DesiredCapacity"]["Default"] == 0

    assert "MaxCapacity" in params
    assert params["MaxCapacity"]["Default"] == 2

    assert "CpuTarget" in params
    assert params["CpuTarget"]["Default"] == 50
    assert params["CpuTarget"]["MinValue"] == 10
    assert params["CpuTarget"]["MaxValue"] == 90


def test_rds_backup_retention_wired(template):
    db = template["Resources"]["DBInstance"]["Properties"]
    retention = db.get("BackupRetentionPeriod")
    assert isinstance(retention, CFTag)
    assert retention.tag == "!Ref"
    assert retention.val == "BackupRetentionDays"


def test_cloudwatch_log_group_retention_7_days(template):
    lg = template["Resources"]["AppLogGroup"]
    assert lg["Properties"].get("RetentionInDays") == 7


def test_iam_instance_role_ssm_managed_policy_and_least_privilege(template):
    role = template["Resources"]["AppInstanceRole"]
    managed_policies = role["Properties"].get("ManagedPolicyArns", [])
    assert "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore" in managed_policies

    # Verify inline policy statements
    doc = role["Properties"]["Policies"][0]["PolicyDocument"]
    statements = {stmt["Sid"]: stmt for stmt in doc["Statement"]}

    assert "S3BucketListAndLocation" in statements
    assert "S3ObjectOperations" in statements
    assert "SecretsManagerRead" in statements
    assert "SsmParameterStoreRead" in statements
    assert "EcrAuthorizationToken" in statements
    assert "EcrPullRepositoryImages" in statements
    assert "CloudWatchLogsLogging" in statements
    assert "StatusPageMonitoringReadOnly" in statements

    # Check SsmParameterStoreRead is strictly scoped to /cloudnotes/*
    ssm_stmt = statements["SsmParameterStoreRead"]
    assert ssm_stmt["Action"] in (
        ["ssm:GetParameter"],
        ["ssm:GetParameter", "ssm:GetParameters", "ssm:GetParametersByPath"]
    ) or "ssm:GetParameter" in ssm_stmt["Action"]


def test_sns_topic_and_subscription(template):
    topic = template["Resources"].get("AlertsTopic")
    assert topic is not None
    assert topic["Type"] == "AWS::SNS::Topic"

    sub = template["Resources"].get("AlertsEmailSubscription")
    assert sub is not None
    assert sub["Type"] == "AWS::SNS::Subscription"
    assert sub["Properties"].get("Protocol") == "email"

    topic_arn = sub["Properties"].get("TopicArn")
    assert isinstance(topic_arn, CFTag)
    assert topic_arn.tag == "!Ref"
    assert topic_arn.val == "AlertsTopic"

    endpoint = sub["Properties"].get("Endpoint")
    assert isinstance(endpoint, CFTag)
    assert endpoint.tag == "!Ref"
    assert endpoint.val == "AlertEmail"


def test_launch_template_properties(template):
    lt = template["Resources"].get("AppLaunchTemplate")
    assert lt is not None
    assert lt["Type"] == "AWS::EC2::LaunchTemplate"

    data = lt["Properties"]["LaunchTemplateData"]
    assert "al2023-ami-kernel-default-x86_64" in str(data.get("ImageId", ""))

    inst_type = data.get("InstanceType")
    assert isinstance(inst_type, CFTag) and inst_type.val == "InstanceType"

    profile = data.get("IamInstanceProfile", {})
    profile_arn = profile.get("Arn")
    assert isinstance(profile_arn, CFTag) and profile_arn.val == "AppInstanceProfile.Arn"

    sec_groups = data.get("SecurityGroupIds", [])
    assert len(sec_groups) == 1
    assert isinstance(sec_groups[0], CFTag) and sec_groups[0].val == "AppSg"

    # IMDSv2 required and hop limit 2
    meta = data.get("MetadataOptions", {})
    assert meta.get("HttpTokens") == "required"
    assert meta.get("HttpPutResponseHopLimit") == 2
    assert meta.get("HttpEndpoint") == "enabled"

    # Detailed monitoring enabled
    assert data.get("Monitoring", {}).get("Enabled") is True

    # Standard CPU credits
    assert data.get("CreditSpecification", {}).get("CpuCredits") == "standard"

    # No SSH Key Name (Session Manager used instead)
    assert "KeyName" not in data


def test_launch_template_user_data(template):
    lt = template["Resources"]["AppLaunchTemplate"]
    user_data_obj = lt["Properties"]["LaunchTemplateData"]["UserData"]
    if isinstance(user_data_obj, dict) and "Fn::Base64" in user_data_obj:
        sub_obj = user_data_obj["Fn::Base64"]
    elif isinstance(user_data_obj, CFTag):
        sub_obj = user_data_obj.val
    else:
        sub_obj = user_data_obj

    raw_script = sub_obj.val if isinstance(sub_obj, CFTag) else str(sub_obj)

    assert "#!/bin/bash" in raw_script
    assert "docker" in raw_script
    assert "systemctl start docker" in raw_script
    assert "ecr get-login-password" in raw_script
    assert "docker run -d --restart always" in raw_script
    assert "-p 8000:8000" in raw_script
    assert "--log-driver awslogs" in raw_script
    assert "DB_SECRET_ARN" in raw_script
    assert "APP_SECRET_ARN" in raw_script
    assert "DB_HOST" in raw_script
    assert "DB_NAME=cloudnotes" in raw_script
    assert "STORAGE_BACKEND=s3" in raw_script
    assert "S3_BUCKET" in raw_script
    assert "AWS_REGION" in raw_script
    assert "ASG_NAME=cloudnotes-asg" in raw_script
    assert "DB_INSTANCE_ID" in raw_script
    assert "COOKIE_SECURE=false" in raw_script

    # Verify no plaintext passwords or sensitive values are hardcoded
    assert "password123" not in raw_script
    assert "secret-key" not in raw_script


def test_application_load_balancer(template):
    alb = template["Resources"].get("AppAlb")
    assert alb is not None
    assert alb["Type"] == "AWS::ElasticLoadBalancingV2::LoadBalancer"
    assert alb["Properties"].get("Scheme") == "internet-facing"
    assert alb["Properties"].get("Type") == "application"

    tg = template["Resources"].get("AppTargetGroup")
    assert tg is not None
    assert tg["Type"] == "AWS::ElasticLoadBalancingV2::TargetGroup"
    assert tg["Properties"].get("Port") == 8000
    assert tg["Properties"].get("Protocol") == "HTTP"
    assert tg["Properties"].get("TargetType") == "instance"
    assert tg["Properties"].get("HealthCheckPath") == "/api/health"
    assert tg["Properties"].get("HealthCheckIntervalSeconds") == 15
    assert tg["Properties"].get("HealthyThresholdCount") == 2
    assert tg["Properties"].get("UnhealthyThresholdCount") == 3

    listener = template["Resources"].get("AppAlbListener")
    assert listener is not None
    assert listener["Type"] == "AWS::ElasticLoadBalancingV2::Listener"
    assert listener["Properties"].get("Port") == 80
    assert listener["Properties"].get("Protocol") == "HTTP"

    actions = listener["Properties"].get("DefaultActions", [])
    assert len(actions) == 1
    assert actions[0].get("Type") == "forward"
    assert isinstance(actions[0].get("TargetGroupArn"), CFTag)
    assert actions[0]["TargetGroupArn"].val == "AppTargetGroup"


def test_auto_scaling_group_and_policy(template):
    asg = template["Resources"].get("AppAsg")
    assert asg is not None
    assert asg["Type"] == "AWS::AutoScaling::AutoScalingGroup"
    assert asg["Properties"].get("AutoScalingGroupName") == "cloudnotes-asg"
    assert asg["Properties"].get("HealthCheckType") == "ELB"
    assert asg["Properties"].get("HealthCheckGracePeriod") == 300

    metrics = asg["Properties"].get("MetricsCollection", [])
    assert len(metrics) >= 1
    assert metrics[0].get("Granularity") == "1Minute"

    # Rolling update policy
    rolling_update = asg.get("UpdatePolicy", {}).get("AutoScalingRollingUpdate")
    assert rolling_update is not None
    assert rolling_update.get("MaxBatchSize") == 1
    assert rolling_update.get("PauseTime") == "PT5M"

    # Target tracking policy
    policy = template["Resources"].get("AppScalingPolicy")
    assert policy is not None
    assert policy["Type"] == "AWS::AutoScaling::ScalingPolicy"
    assert policy["Properties"].get("PolicyType") == "TargetTrackingScaling"

    config = policy["Properties"].get("TargetTrackingConfiguration", {})
    assert config.get("PredefinedMetricSpecification", {}).get("PredefinedMetricType") == "ASGAverageCPUUtilization"
    assert config.get("EstimatedInstanceWarmup") == 120
    assert isinstance(config.get("TargetValue"), CFTag)
    assert config["TargetValue"].val == "CpuTarget"


def test_cloudwatch_alarms_count_and_configuration(template):
    alarms = {
        "AlarmAsgHighCpu": {
            "Namespace": "AWS/EC2",
            "MetricName": "CPUUtilization",
            "Threshold": 70,
            "Period": 60,
            "EvaluationPeriods": 2,
        },
        "AlarmAlbTarget5xx": {
            "Namespace": "AWS/ApplicationELB",
            "MetricName": "HTTPCode_Target_5XX_Count",
            "Threshold": 10,
            "Period": 300,
            "EvaluationPeriods": 1,
        },
        "AlarmAlbUnhealthyHosts": {
            "Namespace": "AWS/ApplicationELB",
            "MetricName": "UnHealthyHostCount",
            "Threshold": 1,
            "Period": 60,
            "EvaluationPeriods": 2,
        },
        "AlarmRdsHighCpu": {
            "Namespace": "AWS/RDS",
            "MetricName": "CPUUtilization",
            "Threshold": 80,
            "Period": 300,
            "EvaluationPeriods": 1,
        },
    }

    for alarm_name, expected in alarms.items():
        alarm = template["Resources"].get(alarm_name)
        assert alarm is not None, f"Missing alarm: {alarm_name}"
        assert alarm["Type"] == "AWS::CloudWatch::Alarm"
        props = alarm["Properties"]
        assert props.get("Namespace") == expected["Namespace"]
        assert props.get("MetricName") == expected["MetricName"]
        assert props.get("Threshold") == expected["Threshold"]
        assert props.get("Period") == expected["Period"]
        assert props.get("EvaluationPeriods") == expected["EvaluationPeriods"]

        actions = props.get("AlarmActions", [])
        assert len(actions) == 1
        assert isinstance(actions[0], CFTag)
        assert actions[0].val == "AlertsTopic"


def test_cloudwatch_dashboard_widgets(template):
    dash = template["Resources"].get("AppDashboard")
    assert dash is not None
    assert dash["Type"] == "AWS::CloudWatch::Dashboard"
    assert dash["Properties"].get("DashboardName") == "cloudnotes"

    raw_body = dash["Properties"]["DashboardBody"]
    if isinstance(raw_body, CFTag):
        raw_body = raw_body.val

    assert "ASG CPU Utilization" in raw_body
    assert "ASG In-Service Instances" in raw_body
    assert "ALB Request Count" in raw_body
    assert "Target Response Time" in raw_body
    assert "ALB Target 5XX Count" in raw_body
    assert "ALB Healthy Host Count" in raw_body
    assert "RDS CPU Utilization" in raw_body
    assert "RDS Database Connections" in raw_body


def test_stage8b_outputs(template):
    outputs = template.get("Outputs", {})
    required = [
        "LoadBalancerUrl",
        "DashboardUrl",
        "DbEndpoint",
        "AlertsTopicArn",
        "LoadBalancerDnsName",
    ]
    for key in required:
        assert key in outputs, f"Missing output: {key}"

    assert "DNSName" in str(outputs["LoadBalancerUrl"]["Value"])
    assert "dashboards:name=cloudnotes" in str(outputs["DashboardUrl"]["Value"])
    assert "Endpoint.Address" in str(outputs["DbEndpoint"]["Value"])
