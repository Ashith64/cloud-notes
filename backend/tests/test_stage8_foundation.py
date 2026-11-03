import os
import re
import yaml
import pytest

FOUNDATION_TEMPLATE_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "infra", "01-foundation.yaml")
)


def _load_cfn_yaml(filepath):
    """Load CloudFormation YAML handling intrinsic tags as dicts/strings."""
    class CfnSafeLoader(yaml.SafeLoader):
        pass

    def default_constructor(loader, tag_suffix, node):
        if isinstance(node, yaml.ScalarNode):
            return {f"!{tag_suffix}": loader.construct_scalar(node)}
        elif isinstance(node, yaml.SequenceNode):
            return {f"!{tag_suffix}": loader.construct_sequence(node)}
        elif isinstance(node, yaml.MappingNode):
            return {f"!{tag_suffix}": loader.construct_mapping(node)}
        return {f"!{tag_suffix}": None}

    CfnSafeLoader.add_multi_constructor("!", default_constructor)

    with open(filepath, "r", encoding="utf-8") as f:
        return yaml.load(f, Loader=CfnSafeLoader)


@pytest.fixture(scope="module")
def template_data():
    assert os.path.exists(FOUNDATION_TEMPLATE_PATH), f"Template missing at {FOUNDATION_TEMPLATE_PATH}"
    with open(FOUNDATION_TEMPLATE_PATH, "r", encoding="utf-8") as f:
        raw_text = f.read()
    data = _load_cfn_yaml(FOUNDATION_TEMPLATE_PATH)
    return {"raw": raw_text, "parsed": data}


def test_template_basics(template_data):
    parsed = template_data["parsed"]
    assert parsed.get("AWSTemplateFormatVersion") == "2010-09-09"
    assert "Description" in parsed
    assert "Parameters" in parsed
    assert "Resources" in parsed
    assert "Outputs" in parsed


def test_parameters(template_data):
    params = template_data["parsed"]["Parameters"]
    assert "ProjectName" in params
    assert params["ProjectName"].get("Default") == "cloudnotes"
    assert "AlertEmail" in params
    assert "Default" not in params["AlertEmail"]  # AlertEmail has no default


def test_vpc_and_networking(template_data):
    resources = template_data["parsed"]["Resources"]
    
    # VPC
    assert "Vpc" in resources
    vpc = resources["Vpc"]
    assert vpc["Type"] == "AWS::EC2::VPC"
    props = vpc["Properties"]
    assert props["CidrBlock"] == "10.0.0.0/16"
    assert props["EnableDnsSupport"] is True
    assert props["EnableDnsHostnames"] is True

    # Internet Gateway
    assert "InternetGateway" in resources
    assert resources["InternetGateway"]["Type"] == "AWS::EC2::InternetGateway"
    assert "VpcGatewayAttachment" in resources
    assert resources["VpcGatewayAttachment"]["Type"] == "AWS::EC2::VPCGatewayAttachment"

    # Route tables
    assert "PublicRouteTable" in resources
    assert "PrivateRouteTable" in resources

    # Public route to 0.0.0.0/0
    assert "PublicDefaultRoute" in resources
    proute = resources["PublicDefaultRoute"]["Properties"]
    assert proute["DestinationCidrBlock"] == "0.0.0.0/0"

    # Private route table has NO 0.0.0.0/0 route
    raw = template_data["raw"]
    assert "PrivateDefaultRoute" not in resources
    assert "NATGateway" not in raw
    assert "NatGateway" not in raw
    assert "AWS::EC2::NatGateway" not in raw


def test_subnets(template_data):
    resources = template_data["parsed"]["Resources"]
    
    # 2 Public subnets
    assert "PublicSubnet1" in resources
    assert "PublicSubnet2" in resources
    ps1 = resources["PublicSubnet1"]["Properties"]
    ps2 = resources["PublicSubnet2"]["Properties"]
    assert ps1["CidrBlock"] == "10.0.1.0/24"
    assert ps2["CidrBlock"] == "10.0.2.0/24"
    assert ps1.get("MapPublicIpOnLaunch") is True
    assert ps2.get("MapPublicIpOnLaunch") is True

    # 2 Private subnets
    assert "PrivateSubnet1" in resources
    assert "PrivateSubnet2" in resources
    priv1 = resources["PrivateSubnet1"]["Properties"]
    priv2 = resources["PrivateSubnet2"]["Properties"]
    assert priv1["CidrBlock"] == "10.0.11.0/24"
    assert priv2["CidrBlock"] == "10.0.12.0/24"


def test_security_groups_and_separate_ingress(template_data):
    resources = template_data["parsed"]["Resources"]
    
    # ALB SG
    assert "AlbSecurityGroup" in resources
    alb_sg = resources["AlbSecurityGroup"]
    assert alb_sg["Type"] == "AWS::EC2::SecurityGroup"
    assert "SecurityGroupIngress" not in alb_sg.get("Properties", {})  # No inline cross-refs

    # App SG
    assert "AppSecurityGroup" in resources
    app_sg = resources["AppSecurityGroup"]
    assert app_sg["Type"] == "AWS::EC2::SecurityGroup"
    assert "SecurityGroupIngress" not in app_sg.get("Properties", {})  # No inline cross-refs

    # DB SG
    assert "DbSecurityGroup" in resources
    db_sg = resources["DbSecurityGroup"]
    assert db_sg["Type"] == "AWS::EC2::SecurityGroup"
    assert "SecurityGroupIngress" not in db_sg.get("Properties", {})  # No inline cross-refs

    # Separate ingress resources
    assert "AlbSecurityGroupIngressHttp" in resources
    assert "AppSecurityGroupIngressFromAlb" in resources
    assert "DbSecurityGroupIngressFromApp" in resources

    alb_ing = resources["AlbSecurityGroupIngressHttp"]["Properties"]
    assert alb_ing["FromPort"] == 80
    assert alb_ing["ToPort"] == 80
    assert alb_ing["CidrIp"] == "0.0.0.0/0"

    app_ing = resources["AppSecurityGroupIngressFromAlb"]["Properties"]
    assert app_ing["FromPort"] == 8000
    assert app_ing["ToPort"] == 8000

    db_ing = resources["DbSecurityGroupIngressFromApp"]["Properties"]
    assert db_ing["FromPort"] == 3306
    assert db_ing["ToPort"] == 3306

    # Verify no port 22 anywhere
    raw = template_data["raw"]
    assert "22" not in re.findall(r"FromPort:\s*(\d+)", raw)
    assert "22" not in re.findall(r"ToPort:\s*(\d+)", raw)


def test_s3_bucket(template_data):
    resources = template_data["parsed"]["Resources"]
    assert "NotesBucket" in resources
    b = resources["NotesBucket"]
    assert b["Type"] == "AWS::S3::Bucket"
    assert b.get("DeletionPolicy") == "Delete"
    props = b["Properties"]
    pab = props["PublicAccessBlockConfiguration"]
    assert pab["BlockPublicAcls"] is True
    assert pab["BlockPublicPolicy"] is True
    assert pab["IgnorePublicAcls"] is True
    assert pab["RestrictPublicBuckets"] is True
    assert props["VersioningConfiguration"]["Status"] == "Enabled"


def test_ecr_repository(template_data):
    resources = template_data["parsed"]["Resources"]
    assert "EcrRepository" in resources
    ecr = resources["EcrRepository"]
    assert ecr["Type"] == "AWS::ECR::Repository"
    assert ecr.get("DeletionPolicy") == "Delete"
    props = ecr["Properties"]
    assert props["EmptyOnDelete"] is True
    assert props["ImageScanningConfiguration"]["ScanOnPush"] is True


def test_sns_topic_and_subscription(template_data):
    resources = template_data["parsed"]["Resources"]
    assert "AlertsTopic" in resources
    assert resources["AlertsTopic"]["Type"] == "AWS::SNS::Topic"
    assert "AlertsEmailSubscription" in resources
    sub = resources["AlertsEmailSubscription"]
    assert sub["Type"] == "AWS::SNS::Subscription"
    assert sub["Properties"]["Protocol"] == "email"


def test_outputs_and_exports(template_data):
    outputs = template_data["parsed"]["Outputs"]
    expected_exports = [
        "VpcId",
        "PublicSubnetIds",
        "PrivateSubnetIds",
        "AlbSecurityGroupId",
        "AppSecurityGroupId",
        "DbSecurityGroupId",
        "BucketName",
        "RepositoryUri",
        "AlertTopicArn",
    ]
    for exp in expected_exports:
        assert exp in outputs, f"Missing output {exp}"
        assert "Export" in outputs[exp], f"Missing Export for {exp}"
