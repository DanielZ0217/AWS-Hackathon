"""Print ingestion configuration and missing resource references; no AWS calls."""

import json
import os
from .bedrock import load_environment


def report():
    load_environment()
    keys = ("AWS_REGION", "INGESTION_MODE", "BEDROCK_KNOWLEDGE_BASE_ID",
            "NEPTUNE_ANALYTICS_GRAPH_ID", "GRAPH_MODEL_ID", "BEDROCK_EMBEDDING_MODEL_ID",
            "BEDROCK_EMBEDDING_DIMENSIONS", "S3_BUCKET", "S3_REFERENCE_PREFIX",
            "S3_PATIENT_PREFIX", "S3_EVALUATION_PREFIX", "S3_GRAPH_IMPORT_PREFIX",
            "OPENSEARCH_ENDPOINT", "OPENSEARCH_INDEX_PREFIX", "NEPTUNE_ENDPOINT",
            "NEPTUNE_PORT", "NEPTUNE_LOAD_ROLE_ARN", "TEXTRACT_REGION")
    values = {key: os.getenv(key, "").strip() for key in keys}
    mode = values["INGESTION_MODE"] or "managed_neptune_graphrag"
    if mode == "managed_neptune_graphrag":
        required_destinations = ("S3_BUCKET", "S3_REFERENCE_PREFIX",
                                 "BEDROCK_KNOWLEDGE_BASE_ID", "NEPTUNE_ANALYTICS_GRAPH_ID")
    elif mode == "custom_opensearch_neptune_database":
        required_destinations = ("S3_BUCKET", "OPENSEARCH_ENDPOINT", "NEPTUNE_ENDPOINT",
                                 "NEPTUNE_LOAD_ROLE_ARN")
    else:
        raise ValueError(f"Unknown ingestion mode: {mode}")
    return {"mode": mode, "settings": values, "missing_cloud_destinations": [key for key in required_destinations
            if not values[key]], "note": "Configuration only; no AWS calls or resources created."}


if __name__ == "__main__":
    print(json.dumps(report(), indent=2))
