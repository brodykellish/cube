"""
Effect manager for DAG renderer.

Handles registration, activation, rebuild, and cleanup of post effects so the
controller does not need per-effect toggle plumbing.
"""

from enum import Enum
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set, Tuple

from cube.dag.effect_node import (
    EffectNode,
    FrameDifferencingEffectNode,
    ImageFlashEffectNode,
)
from cube.shader.shader_loader import load_shader_program
from cube.input.actions import Action


EffectBuilder = Callable[[object, object], List[EffectNode]]


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
        self._builders: Dict[Action, EffectBuilder] = {}
        self._active: Dict[Action, List[EffectNode]] = {}
        self._order: List[Action] = []
        self._shader_cache: Dict[str, object] = {}
        self._redo_stack: List[Action] = []
        self._momentary_active: Set[Action] = set()
        self._held_active: Set[Action] = set()

    def add_effect(self, action: Action, shader_path: str, trigger_mode: TriggerMode, node_class: str = "EffectNode", priority: int = 100):
        """Register an effect associated with an input action."""
        self._registry[action] = EffectRegistration(action, shader_path, trigger_mode, node_class, priority)

    def _ensure_shader(self, shader_path: str):
        if shader_path in self._shader_cache:
            return self._shader_cache[shader_path]
        glsl_version = self.renderer._get_glsl_version()
        shader_program = load_shader_program(shader_path, name=Path(shader_path).stem, glsl_version=glsl_version, vao=self.renderer.vao)
        self._shader_cache[shader_path] = shader_program
        return shader_program

    def _build_nodes(self, reg: EffectRegistration) -> List[EffectNode]:
        if not self.renderer.source_nodes:
            return []
        try:
            shader_program = self._ensure_shader(reg.shader_path)
        except Exception as exc:
            print(f"[EffectManager] Failed to load shader '{reg.shader_path}': {exc}")
            return []

        # Map node class names to actual classes
        node_class_map = {
            'EffectNode': EffectNode,
            'FrameDifferencingEffectNode': FrameDifferencingEffectNode,
            'ImageFlashEffectNode': ImageFlashEffectNode,
        }

        node_class = node_class_map.get(reg.node_class, EffectNode)
        if node_class == EffectNode and reg.node_class != "EffectNode":
            print(f"[EffectManager] Warning: Unknown node_class '{reg.node_class}' for effect '{reg.action.name}'. Using EffectNode.")
            print(f"[EffectManager] Available node classes: {list(node_class_map.keys())}")

        nodes: List[EffectNode] = []
        for i, src in enumerate(self.renderer.source_nodes):
            fx = node_class(
                name=f"{reg.action.name.lower()}_{i}",
                shader=shader_program,
                input_texture=src.output_texture,
                width=src.width,
                height=src.height,
                vao=self.renderer.vao,
            )
            nodes.append(fx)
        return nodes

    def _rebuild_effect_chain(self):
        """
        Rebuild effect chain connections based on priority order.
        
        Effects are sorted by priority (ascending), then by activation order for ties.
        Low priority effects come first (after source), high priority come last.
        """
        if not self._active:
            return
        
        # Get all active effects sorted by priority, then by activation order
        sorted_actions = sorted(
            self._active.keys(),
            key=lambda a: (
                self._registry[a].priority,
                self._order.index(a) if a in self._order else len(self._order)
            )
        )
        
        # For each source node, rebuild the chain
        for i in range(len(self.renderer.source_nodes)):
            source_node = self.renderer.source_nodes[i]
            
            # First, disconnect all effect nodes from this source chain
            # We'll rebuild connections below
            for action in sorted_actions:
                nodes = self._active.get(action, [])
                if i < len(nodes):
                    fx_node = nodes[i]
                    if fx_node in self.renderer.dag.nodes:
                        # Remove all dependencies for this node
                        deps = list(self.renderer.dag.get_dependencies(fx_node))
                        for dep in deps:
                            self.renderer.dag._dependencies[fx_node].discard(dep)
            
            # Now rebuild connections in priority order
            last_node = source_node
            for action in sorted_actions:
                nodes = self._active.get(action, [])
                if i < len(nodes):
                    fx_node = nodes[i]
                    if fx_node in self.renderer.dag.nodes:
                        # Connect: last_node -> fx_node
                        if last_node not in self.renderer.dag.get_dependencies(fx_node):
                            self.renderer.dag.connect(last_node, fx_node)
                        last_node = fx_node

    def _enable(self, action: Action):
        reg = self._registry.get(action)
        if not reg:
            return
        nodes = self._build_nodes(reg)
        if nodes and len(nodes) == len(self.renderer.source_nodes):
            # Add effect nodes to DAG
            for fx_node in nodes:
                self.renderer.dag.add_node(fx_node)
            
            self._active[action] = nodes
            if action not in self._order:
                self._order.append(action)
            if action in self._redo_stack:
                self._redo_stack.remove(action)
            
            # Rebuild effect chain based on priority order
            self._rebuild_effect_chain()
            
            print(f"[EffectManager] Enabled effect '{action.name}' (priority: {reg.priority})")
            self.renderer.dag.print_structure()    
        else:
            print(f"[EffectManager] Effect '{action.name}' not enabled (node count mismatch or empty)")

    def _disable(self, action: Action):
        if action in self._active:
            self._cleanup_effect(action)
            # Rebuild effect chain based on priority order after removal
            self._rebuild_effect_chain()
            print(f"[EffectManager] Disabled effect '{action.name}'")
            self.renderer.dag.print_structure()

    def get_active_chains(self, num_sources: int) -> List[List[EffectNode]]:
        """
        Get active effects grouped per source index, sorted by priority.

        Returns:
            List of length num_sources, each containing the chain of EffectNodes
            to apply for that source, sorted by priority (low to high).
        """
        chains: List[List[EffectNode]] = [[] for _ in range(num_sources)]
        
        # Sort active effects by priority, then by activation order for ties
        sorted_actions = sorted(
            self._active.keys(),
            key=lambda a: (
                self._registry[a].priority,
                self._order.index(a) if a in self._order else len(self._order)
            )
        )
        
        for action in sorted_actions:
            nodes = self._active.get(action, [])
            if len(nodes) != num_sources:
                continue
            for i in range(num_sources):
                chains[i].append(nodes[i])
        return chains

    def get_active_actions(self) -> List[Action]:
        """
        Return active effects in activation order.
        """
        return list(self._order)

    def process_inputs(self, pressed_actions, held_actions):
        """
        React to input state for toggle and momentary effects.
        """
        pressed_set = set(pressed_actions)
        held_set = set(held_actions)

        # Toggle effects: flip on press
        for action, reg in self._registry.items():
            if reg.trigger_mode == TriggerMode.TOGGLE and action in pressed_set:
                if action in self._active:
                    self._disable(action)
                else:
                    self._redo_stack.clear()
                    self._enable(action)

        # Momentary effects: active while held
        for action, reg in self._registry.items():
            if reg.trigger_mode != TriggerMode.MOMENTARY:
                continue
            if action in pressed_set or action in held_set:
                if action not in self._active:
                    self._enable(action)
                self._held_active.add(action)
            else:
                if action in self._active:
                    self._disable(action)
                self._held_active.discard(action)

    def cleanup(self):
        """Cleanup all effects."""
        for action in list(self._active.keys()):
            self._cleanup_effect(action)
        self._order.clear()
        self._registry.clear()
        self._shader_cache.clear()
        self._redo_stack.clear()
        self._momentary_active.clear()

    # Internal helpers
    def _cleanup_effect(self, action: Action):
        nodes = self._active.pop(action, [])
        
        # Remove nodes from DAG
        for node in nodes:
            try:
                self.renderer.dag.remove_node(node)
            except (KeyError, ValueError):
                pass
            try:
                node.cleanup()
            except Exception:
                pass
        if action in self._order:
            self._order.remove(action)

    # -----------------------------------------------------------
    # Undo / Redo
    # -----------------------------------------------------------
    def undo_effect(self) -> bool:
        """
        Disable the most recently activated effect (LIFO) and push it onto the redo stack.

        Returns:
            True if an effect was undone, False otherwise.
        """
        if not self._order:
            return False
        action = self._order[-1]
        self._disable(action)
        self._redo_stack.append(action)
        return True

    def redo_effect(self) -> bool:
        """
        Re-enable the most recently undone effect.

        Returns:
            True if an effect was re-enabled, False otherwise.
        """
        if not self._redo_stack:
            return False
        action = self._redo_stack.pop()
        self._enable(action)
        return True



