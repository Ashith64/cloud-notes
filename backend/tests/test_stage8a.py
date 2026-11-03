"""
Stage 8A CloudFormation Template Validation Tests.
Verifies infra/stack.yaml structure, parameters, resources, least-privilege IAM,
security group rules, S3 encryption and lifecycle, and outputs.
"""
from pathlib import Path
import re
import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
TEMPLATE_PATH = REPO_ROOT / "infra" / "stack.yaml"
README_PATH = REPO_ROOT / "infra" / "README.md"


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


def test_template_header(template):
    assert template.get("AWSTemplateFormatVersion") == "2010-09-09"
    assert "Description" in template


def test_parameters(template):
    params = template.get("Parameters", {})
    expected_params = {
        "ProjectName": "cloudnotes",
        "VpcId": None,
        "SubnetIds": None,
        "AlertEmail": None,
        "ImageTag": "latest",
        "InstanceType": "t3.micro",
        "DBInstanceClass": "db.t3.micro",
        "DesiredCapacity": 0,
        "MaxCapacity": 2,
    }

    for param_name, default_val in expected_params.items():
        assert param_name in params, f"Missing parameter: {param_name}"
        if default_val is not None:
            assert params[param_name].get("Default") == default_val


def test_ecr_repository(template):
    ecr = template["Resources"].get("EcrRepository")
    assert ecr is not None
    assert ecr["Type"] == "AWS::ECR::Repository"
    assert ecr.get("DeletionPolicy") == "Delete"
    assert ecr.get("UpdateReplacePolicy") == "Delete"

    props = ecr["Properties"]
    assert props.get("EmptyOnDelete") is True
    assert props.get("ImageScanningConfiguration", {}).get("ScanOnPush") is True
    assert props.get("ImageTagMutability") == "MUTABLE"

    lifecycle_policy = props.get("LifecyclePolicy", {}).get("LifecyclePolicyText", "")
    assert "imageCountMoreThan" in lifecycle_policy
    assert "expire" in lifecycle_policy


def test_s3_bucket_and_policy(template):
    s3 = template["Resources"].get("NotesBucket")
    assert s3 is not None
    assert s3["Type"] == "AWS::S3::Bucket"
    assert s3.get("DeletionPolicy") == "Retain"
    assert s3.get("UpdateReplacePolicy") == "Retain"

    props = s3["Properties"]
    pab = props.get("PublicAccessBlockConfiguration", {})
    assert pab.get("BlockPublicAcls") is True
    assert pab.get("BlockPublicPolicy") is True
    assert pab.get("IgnorePublicAcls") is True
    assert pab.get("RestrictPublicBuckets") is True

    assert props.get("VersioningConfiguration", {}).get("Status") == "Enabled"

    sse = props.get("BucketEncryption", {}).get("ServerSideEncryptionConfiguration", [])
    assert len(sse) >= 1
    assert sse[0]["ServerSideEncryptionByDefault"]["SSEAlgorithm"] == "AES256"

    rules = props.get("LifecycleConfiguration", {}).get("Rules", [])
    assert len(rules) >= 1
    rule = rules[0]
    assert rule.get("NoncurrentVersionExpiration", {}).get("NoncurrentDays") == 30
    assert rule.get("AbortIncompleteMultipartUpload", {}).get("DaysAfterInitiation") == 7

    policy = template["Resources"].get("NotesBucketPolicy")
    assert policy is not None
    assert policy["Type"] == "AWS::S3::BucketPolicy"
    doc = policy["Properties"]["PolicyDocument"]
    stmt = doc["Statement"][0]
    assert stmt["Effect"] == "Deny"
    assert stmt["Condition"]["Bool"]["aws:SecureTransport"] == "false"


def test_secrets_manager(template):
    secret = template["Resources"].get("AppSecret")
    assert secret is not None
    assert secret["Type"] == "AWS::SecretsManager::Secret"
    assert secret.get("DeletionPolicy") == "Delete"
    props = secret["Properties"]
    gen = props.get("GenerateSecretString", {})
    assert gen.get("SecretStringLength") == 64
    assert gen.get("ExcludePunctuation") is True


def test_security_groups_chain(template):
    alb_sg = template["Resources"].get("AlbSg")
    app_sg = template["Resources"].get("AppSg")
    db_sg = template["Resources"].get("DbSg")

    assert alb_sg is not None and alb_sg["Type"] == "AWS::EC2::SecurityGroup"
    assert app_sg is not None and app_sg["Type"] == "AWS::EC2::SecurityGroup"
    assert db_sg is not None and db_sg["Type"] == "AWS::EC2::SecurityGroup"

    # AlbSg ingress: HTTP 80 from 0.0.0.0/0
    alb_ingress = alb_sg["Properties"].get("SecurityGroupIngress", [])
    assert len(alb_ingress) == 1
    assert alb_ingress[0]["FromPort"] == 80
    assert alb_ingress[0]["ToPort"] == 80
    assert alb_ingress[0]["CidrIp"] == "0.0.0.0/0"

    # AppSg ingress: 8000 only from AlbSg
    app_ingress = app_sg["Properties"].get("SecurityGroupIngress", [])
    assert len(app_ingress) == 1
    assert app_ingress[0]["FromPort"] == 8000
    assert app_ingress[0]["ToPort"] == 8000
    assert isinstance(app_ingress[0]["SourceSecurityGroupId"], CFTag)
    assert app_ingress[0]["SourceSecurityGroupId"].tag == "!Ref"
    assert app_ingress[0]["SourceSecurityGroupId"].val == "AlbSg"

    # DbSg ingress: 3306 only from AppSg
    db_ingress = db_sg["Properties"].get("SecurityGroupIngress", [])
    assert len(db_ingress) == 1
    assert db_ingress[0]["FromPort"] == 3306
    assert db_ingress[0]["ToPort"] == 3306
    assert isinstance(db_ingress[0]["SourceSecurityGroupId"], CFTag)
    assert db_ingress[0]["SourceSecurityGroupId"].tag == "!Ref"
    assert db_ingress[0]["SourceSecurityGroupId"].val == "AppSg"


def test_rds_instance(template):
    subnet_group = template["Resources"].get("DBSubnetGroup")
    assert subnet_group is not None
    assert subnet_group["Type"] == "AWS::RDS::DBSubnetGroup"

    db = template["Resources"].get("DBInstance")
    assert db is not None
    assert db["Type"] == "AWS::RDS::DBInstance"
    assert db.get("DeletionPolicy") == "Delete"
    assert db.get("UpdateReplacePolicy") == "Delete"

    props = db["Properties"]
    assert props.get("Engine") == "mysql"
    assert props.get("EngineVersion") == "8.0"
    assert props.get("AllocatedStorage") == "20"
    assert props.get("StorageType") == "gp3"
    assert props.get("MultiAZ") is False
    assert props.get("PubliclyAccessible") is False
    assert props.get("StorageEncrypted") is True
    assert props.get("BackupRetentionPeriod") == 7
    assert props.get("DeletionProtection") is False
    assert props.get("DeleteAutomatedBackups") is True
    assert props.get("ManageMasterUserPassword") is True
    assert props.get("DBName") == "cloudnotes"
    assert props.get("MasterUsername") == "cloudnotesadmin"


def test_cloudwatch_log_group(template):
    lg = template["Resources"].get("AppLogGroup")
    assert lg is not None
    assert lg["Type"] == "AWS::Logs::LogGroup"
    assert lg.get("DeletionPolicy") == "Delete"
    assert lg["Properties"].get("RetentionInDays") == 14


def test_iam_role_least_privilege(template):
    role = template["Resources"].get("AppInstanceRole")
    assert role is not None
    assert role["Type"] == "AWS::IAM::Role"

    profile = template["Resources"].get("AppInstanceProfile")
    assert profile is not None
    assert profile["Type"] == "AWS::IAM::InstanceProfile"

    doc = role["Properties"]["Policies"][0]["PolicyDocument"]
    statements = {stmt["Sid"]: stmt for stmt in doc["Statement"]}

    assert "S3BucketListAndLocation" in statements
    assert "S3ObjectOperations" in statements
    assert "SecretsManagerRead" in statements
    assert "EcrAuthorizationToken" in statements
    assert "EcrPullRepositoryImages" in statements
    assert "CloudWatchLogsLogging" in statements
    assert "StatusPageMonitoringReadOnly" in statements

    # Verify least privilege scoping
    assert statements["S3BucketListAndLocation"]["Resource"].val == "NotesBucket.Arn"
    assert statements["EcrPullRepositoryImages"]["Resource"].val == "EcrRepository.Arn"
    assert statements["CloudWatchLogsLogging"]["Action"] == [
        "logs:CreateLogStream", "logs:PutLogEvents", "logs:DescribeLogStreams"
    ]
    assert statements["StatusPageMonitoringReadOnly"]["Action"] == [
        "autoscaling:DescribeAutoScalingGroups",
        "cloudwatch:GetMetricStatistics",
        "rds:DescribeDBInstances"
    ]


def test_outputs_defined(template):
    outputs = template.get("Outputs", {})
    required_outputs = [
        "ProjectName",
        "VpcId",
        "SubnetIds",
        "EcrRepositoryUri",
        "EcrRepositoryArn",
        "S3BucketName",
        "S3BucketArn",
        "AppSecretArn",
        "DbSecretArn",
        "DbEndpointAddress",
        "DbEndpointPort",
        "DbName",
        "AlbSecurityGroupId",
        "AppSecurityGroupId",
        "DbSecurityGroupId",
        "LogGroupName",
        "LogGroupArn",
        "InstanceRoleArn",
        "InstanceProfileArn",
        "InstanceProfileName",
    ]
    for out in required_outputs:
        assert out in outputs, f"Missing output: {out}"


def test_readme_exists():
    assert README_PATH.exists()
    content = README_PATH.read_text(encoding="utf-8")
    assert "AlbSg" in content
    assert "AppSg" in content
    assert "DbSg" in content
    assert "NotesBucket" in content
    assert "RetentionInDays" in content or "14 days" in content
    assert "Teardown & Manual Cleanup" in content
    assert "Nothing has been deployed yet" in content
