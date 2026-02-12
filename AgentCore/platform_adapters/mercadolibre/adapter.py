from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class MercadolibreAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Mercado Libre"

    @property
    def supported_actions(self) -> List[str]:
        return ["publication_created", "question_answered", "sale_completed", "reputation_earned", "mercado_shops_activated", "mercado_envios_used", "mercado_pago_integrated", "official_store_applied", "mercado_credito_used", "mercado_ads_managed", "classified_ad_posted", "vehicle_listed"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "mercadolibre" in title or "mercadolibre" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://mercadolibre.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
