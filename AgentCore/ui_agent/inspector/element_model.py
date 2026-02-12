from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple

@dataclass
class ElementModel:
    """Standardized UI element schema."""
    id: str
    role: str # button, textbox, link, image, menu, listitem, etc.
    text: str
    rect: Tuple[int, int, int, int] # x, y, w, h
    enabled: bool = True
    visible: bool = True
    attributes: Dict[str, Any] = field(default_factory=dict)
    parent_id: Optional[str] = None
    children_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "role": self.role,
            "text": self.text,
            "rect": list(self.rect),
            "enabled": self.enabled,
            "visible": self.visible,
            "attributes": self.attributes,
            "parent_id": self.parent_id,
            "children_ids": self.children_ids
        }
