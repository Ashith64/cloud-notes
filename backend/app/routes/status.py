"""System status route (spec C3.5, D5).

GET /api/status  (public, no login required)

Returns:
    instance_id       — EC2 instance ID from IMDSv2 (1-second timeout), else "local"
    availability_zone — EC2 AZ from IMDSv2, else "local"
    running_servers   — instance count from Auto Scaling Group (boto3), null if not configured
    average_cpu       — average CPUUtilization from CloudWatch over past 5 min, null if N/A
    db_ok             — True if SELECT 1 succeeds
    storage_ok        — True if storage.health_check() returns True
    last_backup       — RDS LatestRestorableTime for DB_INSTANCE_ID, null if not configured
    version           — application version string
    uptime_seconds    — seconds since process started

Every section fails gracefully: exceptions are caught, logged, and replaced
with null or False.  The entire response is cached in process memory for 10 s.
"""
import logging
import threading
import time

from flask import Blueprint, current_app, jsonify

from ..storage.factory import get_storage

log = logging.getLogger(__name__)

status_bp = Blueprint("status", __name__, url_prefix="/api")

# Process start time (for uptime_seconds)
_start_time = time.monotonic()

# In-memory cache: (timestamp, response_dict)
_cache_lock = threading.Lock()
_cache: tuple[float, dict] | None = None
_CACHE_TTL = 10.0  # seconds


# ---------------------------------------------------------------------------
# IMDSv2 helpers
# ---------------------------------------------------------------------------

def _imds_token(timeout: float = 0.5) -> str | None:
    """Fetch an IMDSv2 session token.  Returns None on any failure."""
    try:
        import urllib.request
        req = urllib.request.Request(
            "http://169.254.169.254/latest/api/token",
            method="PUT",
            headers={"X-aws-ec2-metadata-token-ttl-seconds": "60"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode()
    except Exception:
        return None


def _imds_get(path: str, token: str, timeout: float = 1.0) -> str | None:
    """Fetch a single metadata value via IMDSv2."""
    try:
        import urllib.request
        req = urllib.request.Request(
            f"http://169.254.169.254/latest/meta-data/{path}",
            headers={"X-aws-ec2-metadata-token": token},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode().strip()
    except Exception:
        return None


def _get_ec2_metadata() -> tuple[str, str]:
    """Return (instance_id, availability_zone); fallback to 'local'."""
    # Fast path: in local development, skip IMDS probing to avoid Windows link-local connect latency
    try:
        if current_app and current_app.config.get("STORAGE_BACKEND", "local") == "local":
            return "local", "local"
    except Exception:
        pass

    token = _imds_token(timeout=0.5)
    if not token:
        return "local", "local"
    instance_id = _imds_get("instance-id", token, timeout=0.5) or "local"
    az = _imds_get("placement/availability-zone", token, timeout=0.5) or "local"
    return instance_id, az


# ---------------------------------------------------------------------------
# ASG / CloudWatch helpers
# ---------------------------------------------------------------------------

def _get_asg_stats(asg_name: str) -> tuple[int | None, float | None]:
    """Return (running_servers, average_cpu).  Both None on any error."""
    if not asg_name:
        return None, None
    try:
        import boto3
        from datetime import datetime, timedelta, timezone

        region = current_app.config.get("AWS_REGION") if current_app else None
        session = boto3.Session(region_name=region) if region else boto3.Session()
        asg_client = session.client("autoscaling")
        cw_client = session.client("cloudwatch")

        # Running instance count
        resp = asg_client.describe_auto_scaling_groups(AutoScalingGroupNames=[asg_name])
        groups = resp.get("AutoScalingGroups", [])
        if not groups:
            return None, None
        instances = [i for i in groups[0].get("Instances", []) if i.get("LifecycleState") == "InService"]
        running = len(instances)

        # Average CPUUtilization over the last 10 minutes
        now = datetime.now(timezone.utc)
        start = now - timedelta(minutes=10)
        cw_resp = cw_client.get_metric_statistics(
            Namespace="AWS/EC2",
            MetricName="CPUUtilization",
            Dimensions=[{"Name": "AutoScalingGroupName", "Value": asg_name}],
            StartTime=start,
            EndTime=now,
            Period=300,
            Statistics=["Average"],
        )
        datapoints = cw_resp.get("Datapoints", [])
        if datapoints:
            sorted_dp = sorted(datapoints, key=lambda d: d.get("Timestamp"))
            avg_cpu = round(sorted_dp[-1]["Average"], 2)
        else:
            avg_cpu = None

        return running, avg_cpu
    except Exception as exc:
        log.debug("ASG/CW stats failed: %s", exc)
        return None, None


def _get_last_backup(db_instance_id: str) -> str | None:
    """Return ISO-8601 LatestRestorableTime or None."""
    if not db_instance_id:
        return None
    try:
        import boto3
        region = current_app.config.get("AWS_REGION") if current_app else None
        rds = boto3.client("rds", region_name=region) if region else boto3.client("rds")
        resp = rds.describe_db_instances(DBInstanceIdentifier=db_instance_id)
        instances = resp.get("DBInstances", [])
        if not instances:
            return None
        ts = instances[0].get("LatestRestorableTime")
        return ts.isoformat() if ts else None
    except Exception as exc:
        log.debug("RDS last-backup failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# DB health helper
# ---------------------------------------------------------------------------

def _db_ok() -> bool:
    try:
        from sqlalchemy import text
        db = current_app._db_session()
        db.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        log.debug("DB health check failed: %s", exc)
        return False


# ---------------------------------------------------------------------------
# GET /api/status
# ---------------------------------------------------------------------------

@status_bp.route("/status", methods=["GET"])
def system_status():
    """Public endpoint — returns live system status, cached for 10 seconds."""
    global _cache

    now = time.monotonic()

    with _cache_lock:
        if _cache is not None:
            cached_at, data = _cache
            if now - cached_at < _CACHE_TTL:
                return jsonify(data), 200

    # Build fresh response (outside the lock to avoid blocking other requests)
    cfg = current_app.config

    instance_id, az = _get_ec2_metadata()
    asg_name = cfg.get("ASG_NAME", "")
    running_servers, average_cpu = _get_asg_stats(asg_name)
    db_instance_id = cfg.get("DB_INSTANCE_ID", "")
    last_backup = _get_last_backup(db_instance_id)

    storage_healthy = False
    try:
        storage_healthy = get_storage().health_check()
    except Exception as exc:
        log.debug("Storage health check failed: %s", exc)

    data = {
        "instance_id": instance_id,
        "availability_zone": az,
        "running_servers": running_servers,
        "average_cpu": average_cpu,
        "db_ok": _db_ok(),
        "storage_ok": storage_healthy,
        "last_backup": last_backup,
        "version": cfg.get("APP_VERSION", "0.1.0"),
        "uptime_seconds": round(now - _start_time),
    }

    with _cache_lock:
        _cache = (now, data)

    return jsonify(data), 200
