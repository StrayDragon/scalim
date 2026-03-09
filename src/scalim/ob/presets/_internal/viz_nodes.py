from typing import Any, Dict, Optional, Set, cast


class VizObserverNodeMixin:
    snapshot: Optional[Dict[str, Any]] = None
    _known_node_ids: Optional[Set[str]] = None
    _node_id_cache: Optional[Dict[str, str]] = None

    def _get_node_id_cache(self) -> Dict[str, str]:
        cache = self._node_id_cache
        if cache is None:
            cache = {}
            self._node_id_cache = cache
        return cache

    @staticmethod
    def _canonical_loader_name(value: Any) -> str:
        raw = str(value or "").strip()
        if not raw:
            return ""
        if " " in raw:
            return raw.split(" ", 1)[0].strip()
        return raw

    def _get_known_node_ids(self) -> Set[str]:
        if self._known_node_ids is not None:
            return self._known_node_ids
        known: Set[str] = set()
        snapshot = self.snapshot
        if snapshot and isinstance(snapshot, dict):
            nodes = snapshot.get("nodes")
            if isinstance(nodes, list):
                typed_nodes = cast("list[Dict[str, Any]]", nodes)
                for typed_item_dict in typed_nodes:
                    node_id = typed_item_dict.get("id")
                    if node_id:
                        known.add(str(node_id))
        self._known_node_ids = known
        return known

    def _normalize_node_ref_id(self, node_id: str) -> str:
        raw = str(node_id or "").strip()
        if not raw:
            return ""
        cache = self._get_node_id_cache()
        cached = cache.get(raw)
        if cached is not None:
            return cached

        known = self._get_known_node_ids()
        if not known or raw in known:
            cache[raw] = raw
            return raw

        if " " in raw:
            trimmed = raw.split(" ", 1)[0].strip()
            if trimmed in known:
                cache[raw] = trimmed
                return trimmed

        if raw.startswith("field:"):
            prefix = "{}_".format(raw)
            candidates = [item for item in known if item.startswith(prefix)]
            if candidates:
                value = None
                for item in candidates:
                    if item.endswith("_value"):
                        value = item
                        break
                chosen = value or sorted(candidates)[0]
                cache[raw] = chosen
                return chosen

        cache[raw] = raw
        return raw

    def _normalize_node_ref(self, node_ref: Dict[str, str]) -> Dict[str, str]:
        raw_id = node_ref.get("id", "")
        if not raw_id:
            return node_ref
        normalized = self._normalize_node_ref_id(raw_id)
        if normalized and normalized != raw_id:
            return {"type": node_ref.get("type", ""), "id": normalized}
        return node_ref
