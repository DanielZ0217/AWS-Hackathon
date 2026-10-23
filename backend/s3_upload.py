"""Upload one bundled patient to its own S3 bucket.   .venv/bin/python -m backend.s3_upload VP01

Creates the bucket if needed with: default encryption (SSE-S3), all public access blocked, and a
policy that refuses any request not made over TLS. Needs AWS credentials in the environment.
"""
from __future__ import annotations

import json
import sys

import boto3
from botocore.exceptions import ClientError

from .store import DATA_ROOT, REGION, bucket_name_for


def upload(patient_id: str) -> str:
    account = boto3.client("sts", region_name=REGION).get_caller_identity()["Account"]
    bucket = bucket_name_for(patient_id, account)
    s3 = boto3.client("s3", region_name=REGION)

    try:
        s3.head_bucket(Bucket=bucket)
    except ClientError:
        s3.create_bucket(Bucket=bucket)  # us-east-1 needs no LocationConstraint
    s3.put_public_access_block(
        Bucket=bucket,
        PublicAccessBlockConfiguration={
            "BlockPublicAcls": True,
            "IgnorePublicAcls": True,
            "BlockPublicPolicy": True,
            "RestrictPublicBuckets": True,
        },
    )
    s3.put_bucket_encryption(
        Bucket=bucket,
        ServerSideEncryptionConfiguration={"Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]},
    )
    s3.put_bucket_policy(
        Bucket=bucket,
        Policy=json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Sid": "DenyInsecureTransport",
                        "Effect": "Deny",
                        "Principal": "*",
                        "Action": "s3:*",
                        "Resource": [f"arn:aws:s3:::{bucket}", f"arn:aws:s3:::{bucket}/*"],
                        "Condition": {"Bool": {"aws:SecureTransport": "false"}},
                    }
                ],
            }
        ),
    )

    root = DATA_ROOT / patient_id
    files = [p for p in root.rglob("*") if p.is_file()]
    for path in files:
        s3.upload_file(str(path), bucket, path.relative_to(root).as_posix())
    print(f"uploaded {len(files)} files to s3://{bucket}")
    return bucket


if __name__ == "__main__":
    upload(sys.argv[1] if len(sys.argv) > 1 else "VP01")
