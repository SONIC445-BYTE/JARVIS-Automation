from typing import Dict, List
from ..base_adapter import BaseAdapter, Plan
from ...intent_planner import ExecutionStep
import urllib.parse

class RedditAdapter(BaseAdapter):
    @property
    def platform_name(self) -> str:
        return "Reddit"

    @property
    def supported_actions(self) -> List[str]:
        return ["post_submitted", "comment_posted", "upvote_given", "downvote_given", "subreddit_joined", "award_given", "crosspost_created", "wiki_edited", "poll_voted", "prediction_made", "avatar_customized", "community_chat_joined"]

    def detect_ui(self, ui_tree: Dict) -> bool:
        title = ui_tree.get("active_window", "").lower()
        return "reddit" in title or "reddit" in title

    def build_plan(self, action_name: str, params: Dict) -> Plan:
        steps = []
        query = urllib.parse.quote(str(params.get("query", params.get("text", ""))))
        url = f"https://reddit.com/?action={action_name}&q={query}"
        steps.append(ExecutionStep(action="navigate", target=url, parameters={"url": url}))
        return Plan(steps=steps, confidence=0.85)

    def verify_action_result(self, ui_snapshot: Dict) -> bool:
        return True
