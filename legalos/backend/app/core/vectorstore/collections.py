from qdrant_client.http import models as qmodels
from app.core.vectorstore.qdrant_client import get_qdrant_client

def init_collections() -> None:
    """
    Idempotently creates all collections needed in LegalOS.
    Called at app startup during lifespans.
    """
    client = get_qdrant_client()
    
    # We define all collections used in the application here
    # In Part 1, we only have contract_clauses
    collections_config = {
        "contract_clauses": {
            "size": 384,
            "distance": qmodels.Distance.COSINE
        },
        "legal_notices": {
            "size": 384,
            "distance": qmodels.Distance.COSINE
        },
        "knowledge_base": {
            "size": 384,
            "distance": qmodels.Distance.COSINE
        }
    }

    
    print("[QDRANT] Running collection warming/creation...")
    
    for name, config in collections_config.items():
        try:
            # Check if exists
            exists = client.collection_exists(collection_name=name)
            if not exists:
                print(f"[QDRANT] Collection '{name}' does not exist. Creating...")
                client.create_collection(
                    collection_name=name,
                    vectors_config=qmodels.VectorParams(
                        size=config["size"],
                        distance=config["distance"]
                    )
                )
                print(f"[QDRANT] Collection '{name}' initialized.")
            else:
                print(f"[QDRANT] Collection '{name}' is already active.")
        except Exception as e:
            print(f"[QDRANT] Critical: Failed to initialize Qdrant collection '{name}': {str(e)}")
            raise e
