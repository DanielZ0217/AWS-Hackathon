"""Where patient files live.

The demo reads the BUNDLED local copy of one hardcoded patient, so it cannot fail on the network.
The same layout can be served from S3 (one bucket per patient) by setting DATA_SOURCE=s3.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

DATA_ROOT = Path(__file__).parent / "data" / "patients"
DEMO_PATIENT = os.environ.get("DEMO_PATIENT", "VP01")
DATA_SOURCE = os.environ.get("DATA_SOURCE", "local")  # "local" (default) or "s3"
S3_BUCKET_PREFIX = os.environ.get("S3_BUCKET_PREFIX", "care-demo")
REGION = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")


@dataclass(frozen=True)
class Visit:
    index: int
    day: int
    ecg_record: str  # path to the ECG without its extension, e.g. "t0_day0/47212598"
    xray_file: str  # e.g. "t0_day0/00004344_037.png"
    ecg: dict[str, Any]  # machine report and measurements from the dataset
    xray: dict[str, Any]  # reference labels and view from the dataset


@dataclass(frozen=True)
class Patient:
    patient_id: str
    age: int
    sex: str
    provenance: str
    visits: tuple[Visit, ...]


class FileStore(Protocol):
    name: str

    def read(self, patient_id: str, relpath: str) -> bytes: ...


class LocalStore:
    name = "local"

    def __init__(self, root: Path = DATA_ROOT) -> None:
        self.root = root.resolve()

    def read(self, patient_id: str, relpath: str) -> bytes:
        path = (self.root / patient_id / relpath).resolve()
        if self.root not in path.parents:  # never read outside the data folder
            raise ValueError("path is outside the data folder")
        return path.read_bytes()


class S3Store:
    """One bucket per patient, named <prefix>-<patient id>-<account id>, keys as in the local layout."""

    name = "s3"

    def __init__(self) -> None:
        import boto3

        self._s3 = boto3.client("s3", region_name=REGION)
        self._account = boto3.client("sts", region_name=REGION).get_caller_identity()["Account"]

    def bucket_name(self, patient_id: str) -> str:
        return bucket_name_for(patient_id, self._account)

    def read(self, patient_id: str, relpath: str) -> bytes:
        return self._s3.get_object(Bucket=self.bucket_name(patient_id), Key=relpath)["Body"].read()


def bucket_name_for(patient_id: str, account_id: str) -> str:
    # Bucket names are global, so the account id keeps them unique.
    return f"{S3_BUCKET_PREFIX}-{patient_id.lower()}-{account_id}"


def load_patient(store: FileStore, patient_id: str) -> Patient:
    raw = json.loads(store.read(patient_id, "patient.json"))
    visits = tuple(
        Visit(
            index=v["index"],
            day=v["day"],
            ecg_record=v["ecg_record"],
            xray_file=v["xray_file"],
            ecg=v["ecg"],
            xray=v["xray"],
        )
        for v in sorted(raw["visits"], key=lambda v: v["index"])
    )
    return Patient(raw["patient_id"], raw["age"], raw["sex"], raw.get("provenance", ""), visits)


def get_store() -> FileStore:
    return S3Store() if DATA_SOURCE == "s3" else LocalStore()
