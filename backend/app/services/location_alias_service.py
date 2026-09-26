"""Location Alias & Entity Index Service for fast offline lookup and phonetic resolution."""
import logging
import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from rapidfuzz import fuzz, process

logger = logging.getLogger("voxentra.location_alias_service")

class LocationAliasService:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LocationAliasService, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._index: Dict[str, Any] = {}
        self._alias_map: Dict[str, List[Dict[str, Any]]] = {}
        self._all_alias_keys: List[str] = []
        self.load_index()
        self._initialized = True

    def load_index(self):
        """Loads serialized location index cache from disk."""
        index_path = Path(__file__).resolve().parent.parent.parent.parent / "data" / "location" / "coimbatore_location_index.json"
        if not index_path.exists():
            logger.warning(f"Index file {index_path} not found. In-memory fallback will be empty.")
            return

        try:
            with open(index_path, "r", encoding="utf-8") as f:
                self._index = json.load(f)
            self._alias_map = self._index.get("alias_to_entity", {})
            self._all_alias_keys = list(self._alias_map.keys())
            logger.info(f"Loaded {len(self._all_alias_keys)} alias search keys from Coimbatore Location Index.")
        except Exception as e:
            logger.error(f"Failed to load location index: {e}")

    def lookup_exact(self, query: str) -> List[Dict[str, Any]]:
        """Performs exact and normalized alias matching."""
        if not query:
            return []
        q = query.lower().strip()
        q_clean = q.replace(" ", "").replace("-", "").replace(".", "")

        results = []
        # Direct lookup
        if q in self._alias_map:
            results.extend(self._alias_map[q])
            
        # Cleaned key lookup
        for k, v in self._alias_map.items():
            k_clean = k.replace(" ", "").replace("-", "").replace(".", "")
            if k_clean == q_clean and v not in results:
                results.extend(v)

        return results

    def lookup_fuzzy(self, query: str, threshold: float = 80.0, limit: int = 5) -> List[Tuple[Dict[str, Any], float]]:
        """Performs rapid phonetic and fuzzy matching across all registered aliases."""
        if not query or not self._all_alias_keys:
            return []
        q = query.lower().strip()
        
        matches = process.extract(
            q,
            self._all_alias_keys,
            scorer=fuzz.token_sort_ratio,
            limit=limit,
            score_cutoff=threshold
        )
        
        res = []
        for matched_key, score, _ in matches:
            norm_score = round(score / 100.0, 2)
            for entity in self._alias_map.get(matched_key, []):
                res.append((entity, norm_score))
        return res

    def get_entity_details(self, entity_type: str, entity_id: int) -> Optional[Dict[str, Any]]:
        """Fetches full entity dictionary from index."""
        type_key_map = {
            "taluk": "taluks",
            "firka": "firkas",
            "revenue_village": "villages",
            "zone": "zones",
            "ward": "wards",
            "area": "areas",
            "street": "streets",
            "landmark": "landmarks"
        }
        section = type_key_map.get(entity_type.lower())
        if not section or section not in self._index:
            return None
        return self._index[section].get(str(entity_id))

location_alias_service = LocationAliasService()
