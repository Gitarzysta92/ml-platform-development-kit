import os


def _as_bool(value: str, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class Settings:
    app_env = os.getenv("APP_ENV", "development")

    mysql_host = os.getenv("MYSQL_HOST", "localhost")
    mysql_port = int(os.getenv("MYSQL_PORT", "3306"))
    mysql_db = os.getenv("MYSQL_DB", "ml_jobs")
    mysql_user = os.getenv("MYSQL_USER", "ml_user")
    mysql_password = os.getenv("MYSQL_PASSWORD", "")

    rabbitmq_host = os.getenv("RABBITMQ_HOST", "localhost")
    rabbitmq_port = int(os.getenv("RABBITMQ_PORT", "5672"))
    rabbitmq_user = os.getenv("RABBITMQ_USER", "guest")
    rabbitmq_password = os.getenv("RABBITMQ_PASSWORD", "guest")
    rabbitmq_queue = os.getenv("RABBITMQ_QUEUE", "gpu-jobs")

    runpod_api_base_url = os.getenv("RUNPOD_API_BASE_URL", "https://api.runpod.ai/v2").rstrip("/")
    runpod_endpoint_id = os.getenv("RUNPOD_ENDPOINT_ID", "")
    runpod_api_key = os.getenv("RUNPOD_API_KEY", "")
    runpod_status_poll_interval_seconds = int(os.getenv("RUNPOD_STATUS_POLL_INTERVAL_SECONDS", "3"))
    runpod_status_timeout_seconds = int(os.getenv("RUNPOD_STATUS_TIMEOUT_SECONDS", "900"))

    s3_endpoint_url = os.getenv("S3_ENDPOINT_URL", "")
    s3_region = os.getenv("S3_REGION", "us-east-1")
    s3_bucket = os.getenv("S3_BUCKET", "")
    s3_access_key_id = os.getenv("S3_ACCESS_KEY_ID", "")
    s3_secret_access_key = os.getenv("S3_SECRET_ACCESS_KEY", "")
    s3_force_path_style = _as_bool(os.getenv("S3_FORCE_PATH_STYLE"), default=False)
    s3_output_prefix = os.getenv("S3_OUTPUT_PREFIX", "runpod-results")
    mlflow_tracking_uri = os.getenv("MLFLOW_TRACKING_URI", "")
    mlflow_experiment_name = os.getenv("MLFLOW_EXPERIMENT_NAME", "runpod-jobs")


settings = Settings()

