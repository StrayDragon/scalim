# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false, reportUnknownParameterType=false, reportUnknownLambdaType=false, reportMissingParameterType=false, reportAttributeAccessIssue=false, reportUnknownMemberType=false, reportUnannotatedClassAttribute=false, reportUninitializedInstanceVariable=false, reportPrivateUsage=false, reportCallIssue=false, reportArgumentType=false, reportUnusedFunction=false, reportImplicitOverride=false, reportUnusedImport=false, reportMissingTypeArgument=false, reportUnnecessaryComparison=false, reportUnnecessaryCast=false
from typing import Any, Dict, Sequence, Set, cast


class VizObserverNodeMixin:
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
        if self.snapshot and isinstance(self.snapshot, dict):
            nodes = self.snapshot.get("nodes")
            if isinstance(nodes, list):
                for item_dict in cast("Sequence[Dict[str, Any]]", nodes):
                    node_id = item_dict.get("id")
                    if node_id:
                        known.add(str(node_id))
        self._known_node_ids = known
        return known

    def _normalize_node_ref_id(self, node_id: str) -> str:
        raw = str(node_id or "").strip()
        if not raw:
            return ""
        cached = self._node_id_cache.get(raw)
        if cached is not None:
            return cached

        known = self._get_known_node_ids()
        if not known or raw in known:
            self._node_id_cache[raw] = raw
            return raw

        if " " in raw:
            trimmed = raw.split(" ", 1)[0].strip()
            if trimmed in known:
                self._node_id_cache[raw] = trimmed
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
                self._node_id_cache[raw] = chosen
                return chosen

        self._node_id_cache[raw] = raw
        return raw

    def _normalize_node_ref(self, node_ref: Dict[str, str]) -> Dict[str, str]:
        raw_id = node_ref.get("id", "")
        if not raw_id:
            return node_ref
        normalized = self._normalize_node_ref_id(raw_id)
        if normalized and normalized != raw_id:
            return {"type": node_ref.get("type", ""), "id": normalized}
        return node_ref
