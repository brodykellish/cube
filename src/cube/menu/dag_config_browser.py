"""
Menu state for browsing and loading saved DAG configurations.
"""
from pathlib import Path
from typing import Optional, List
from .menu_states import MenuState
from .menu_context import MenuContext
from .menu_renderer import MenuRenderer
from .menu_utils import ScrollableList, MenuHeader
from .actions import MenuAction, BackAction, LoadDAGConfigAction, SaveDAGConfigAction
from .text_input_prompt import TextInputPrompt


class DAGConfigBrowser(MenuState):
    """Browse and load saved DAG configurations."""
    
    def __init__(self, configs_dir: Path):
        """
        Initialize DAG config browser.
        
        Args:
            configs_dir: Directory containing saved DAG configurations
        """
        super().__init__('dag_config_browser')
        self.configs_dir = configs_dir
        self.configs_dir.mkdir(parents=True, exist_ok=True)
        
        self.items = []
        self.list = ScrollableList(self.items)
        self._refresh_configs()
    
    def _refresh_configs(self):
        """Refresh the list of available configurations."""
        self.items = []
        
        if self.configs_dir.exists():
            for config_file in sorted(self.configs_dir.glob("*.yaml")):
                self.items.append(("config", config_file.stem, config_file))
            for config_file in sorted(self.configs_dir.glob("*.yml")):
                self.items.append(("config", config_file.stem, config_file))
        
        if not self.items:
            self.items.append(("info", "NO CONFIGS FOUND", None))
        
        self.items.append(("action", "SAVE CURRENT CONFIG", "save"))
        self.items.append(("action", "BACK", None))
        self.list.set_items(self.items)
    
    def render(self, renderer: MenuRenderer, context: MenuContext):
        """Render the config browser."""
        renderer.clear((0, 0, 0))
        
        header_height = MenuHeader.render(renderer, "SAVED CONFIGURATIONS")
        
        available_height = context.height - header_height
        
        def format_item(item):
            item_type, name, _ = item
            if item_type == "config":
                return f"  {name}"
            elif item_type == "info":
                return f"  {name}"
            elif item_type == "action":
                return f"< {name}"
            return name
        
        self.list.render(
            renderer, context,
            y_start=header_height,
            available_height=available_height,
            format_item=format_item,
            selected_color=(255, 255, 100),
            normal_color=(200, 200, 200)
        )
    
    def handle_input(self, key: str, context: MenuContext) -> Optional[MenuAction]:
        """Handle input."""
        if key == 'up':
            self.list.move_up()
        elif key == 'down':
            self.list.move_down()
        elif key == 'enter':
            selected = self.list.get_selected()
            if selected:
                item_type, name, data = selected
                
                if item_type == "config":
                    return LoadDAGConfigAction(config_path=data)
                elif item_type == "action" and data == "save":
                    # Return a special action that will trigger text input prompt
                    # We'll handle this in the dev_menu to show the text input prompt
                    return SaveDAGConfigAction(filename="")
                elif item_type == "action" and name == "BACK":
                    return BackAction()
        elif key in ('back', 'escape'):
            return BackAction()
        
        return None

