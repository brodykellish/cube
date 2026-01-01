"""
Effect manager for DAG renderer.
"""

from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

from cube.dag.effect_node import (
    EffectNode,
    FrameDifferencingEffectNode,
    ImageFlashEffectNode,
    MiniatureOverlayEffectNode,
    TemporalShatterEffectNode,
)
from cube.dag.node import Node
from cube.shader.shader_loader import load_shader_program
from cube.input.actions import Action


class TriggerMode(Enum):
    TOGGLE = "toggle"
    MOMENTARY = "momentary"


class EffectRegistration:
    def __init__(self, action: Action, shader_path: str, trigger_mode: TriggerMode, node_class: str = "EffectNode", priority: int = 100):
        self.action = action
        self.shader_path = shader_path
        self.trigger_mode = trigger_mode
        self.node_class = node_class
        self.priority = priority


class EffectManager:
    """
    Manages lifecycle of DAG post effects.

    - Register effects with a builder callable that creates EffectNodes when invoked.
    - Toggle effects on/off by name.
    - Cleanup all effects on shutdown.
    """

    def __init__(self, renderer):
        self.renderer = renderer
        self._registry: Dict[Action, EffectRegistration] = {}
        self._active: Dict[Action, List[EffectNode]] = {}
        self._order: List[Action] = []
        self._shader_cache: Dict[str, object] = {}
        self._redo_stack: List[Action] = []

    def add_effect(self, action: Action, shader_path: str, trigger_mode: TriggerMode, node_class: str = "EffectNode", priority: int = 100):
        """Register an effect associated with an input action."""
        self._registry[action] = EffectRegistration(action, shader_path, trigger_mode, node_class, priority)

    def _ensure_shader(self, shader_path: str):
        if shader_path in self._shader_cache:
            return self._shader_cache[shader_path]
        glsl_version = self.renderer.get_glsl_version()
        shader_program = load_shader_program(shader_path, name=Path(shader_path).stem, glsl_version=glsl_version, vao=self.renderer.vao)
        self._shader_cache[shader_path] = shader_program
        return shader_program

    def _build_nodes(self, reg: EffectRegistration, dag) -> List[EffectNode]:
        if not dag or not dag.root_nodes:
            return []
        
        shader_program = self._ensure_shader(reg.shader_path)
        node_class = {
            'EffectNode': EffectNode,
            'FrameDifferencingEffectNode': FrameDifferencingEffectNode,
            'ImageFlashEffectNode': ImageFlashEffectNode,
            'MiniatureOverlayEffectNode': MiniatureOverlayEffectNode,
            'TemporalShatterEffectNode': TemporalShatterEffectNode,
        }.get(reg.node_class, EffectNode)

        nodes = []
        for i, src in enumerate(dag.root_nodes):
            fx = node_class(
                name=f"{reg.action.name.lower()}_{i}",
                shader=shader_program,
                input_texture=None,
                width=src.width,
                height=src.height,
                vao=self.renderer.vao,
            )
            nodes.append(fx)
        return nodes

    def _find_insertion_point(self, dag, source_index: int, new_priority: int) -> Optional[Node]:
        """Find where to insert a new effect node based on priority, with tiebreak to end."""
        if source_index >= len(dag.root_nodes):
            return dag.root_nodes[0] if dag.root_nodes else None
        
        current = dag.root_nodes[source_index]
        sorted_actions = sorted(
            self._active.keys(),
            key=lambda a: (
                self._registry[a].priority,
                self._order.index(a) if a in self._order else len(self._order)
            )
        )
        
        # Find insertion point based on priority
        for action in sorted_actions:
            action_priority = self._registry[action].priority
            # If we find an effect with strictly higher priority, insert before it
            if action_priority > new_priority:
                nodes = self._active.get(action, [])
                if source_index < len(nodes):
                    effect_node = nodes[source_index]
                    if effect_node.parent == current:
                        return current
            # If priority is equal, skip (tiebreak: append to end)
            elif action_priority == new_priority:
                # Continue following chain but don't insert here
                nodes = self._active.get(action, [])
                if source_index < len(nodes):
                    effect_node = nodes[source_index]
                    if effect_node.parent == current:
                        current = effect_node
            # If priority is less, continue following chain
            else:
                nodes = self._active.get(action, [])
                if source_index < len(nodes):
                    effect_node = nodes[source_index]
                    if effect_node.parent == current:
                        current = effect_node
        
        # Append to end of chain (either no higher priority found, or tiebreak)
        return current

    def _enable(self, action: Action, dag):
        reg = self._registry.get(action)
        if not reg or not dag:
            return
        
        nodes = self._build_nodes(reg, dag)
        if not nodes or len(nodes) != len(dag.root_nodes):
            return
        
        for fx_node in nodes:
            dag.add_node(fx_node)
        
        self._active[action] = nodes
        if action not in self._order:
            self._order.append(action)
        if action in self._redo_stack:
            self._redo_stack.remove(action)
        
        for i, fx_node in enumerate(nodes):
            insertion_point = self._find_insertion_point(dag, i, reg.priority)
            if insertion_point:
                children = list(insertion_point.children)
                dag.connect(insertion_point, fx_node)
                for child in children:
                    dag.disconnect(child)
                    dag.connect(fx_node, child)
        
        dag.print_dag()

    def _disable(self, action: Action, dag):
        if action not in self._active:
            return
        
        nodes = self._active.get(action, [])
        for fx_node in nodes:
            if fx_node.parent:
                parent = fx_node.parent
                children = list(fx_node.children)
                dag.disconnect(fx_node)
                for child in children:
                    dag.connect(parent, child)
        
        self._cleanup_effect(action, dag)
        dag.print_dag()


    def get_active_actions(self) -> List[Action]:
        """
        Return active effects in activation order.
        """
        return list(self._order)
    
    def trigger_effect(self, action: Action, dag):
        """Public method to enable an effect."""
        if action not in self._active:
            self._enable(action, dag)
    
    def untoggle_effect(self, action: Action, dag):
        """Public method to disable an effect."""
        if action in self._active:
            self._disable(action, dag)

    def process_inputs(self, pressed_actions, held_actions, dag):
        """React to input state for toggle and momentary effects."""
        pressed_set = set(pressed_actions)
        held_set = set(held_actions)

        for action, reg in self._registry.items():
            if reg.trigger_mode == TriggerMode.TOGGLE and action in pressed_set:
                if action in self._active:
                    self._disable(action, dag)
                else:
                    self._redo_stack.clear()
                    self._enable(action, dag)
            elif reg.trigger_mode == TriggerMode.MOMENTARY:
                should_be_active = action in pressed_set or action in held_set
                is_active = action in self._active
                if should_be_active and not is_active:
                    self._enable(action, dag)
                elif not should_be_active and is_active:
                    self._disable(action, dag)

    def cleanup(self, dag=None):
        """Cleanup all effects."""
        for action in list(self._active.keys()):
            self._cleanup_effect(action, dag)
        self._order.clear()
        self._registry.clear()
        self._shader_cache.clear()
        self._redo_stack.clear()

    def _cleanup_effect(self, action: Action, dag):
        nodes = self._active.pop(action, [])
        for node in nodes:
            if dag:
                dag.remove_node(node)
            node.cleanup()
        if action in self._order:
            self._order.remove(action)

    def undo_effect(self, dag) -> bool:
        """Disable the most recently activated effect."""
        if not self._order:
            return False
        action = self._order[-1]
        self._disable(action, dag)
        self._redo_stack.append(action)
        return True

    def redo_effect(self, dag) -> bool:
        """Re-enable the most recently undone effect."""
        if not self._redo_stack:
            return False
        action = self._redo_stack.pop()
        self._enable(action, dag)
        return True



