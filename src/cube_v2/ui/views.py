"""
UI view components for cube_v2 TUI.

Provides different views for displaying DAG, parameters, mappings, etc.
"""

from typing import List, Dict
from ..dag.dag import DAG
from ..dag.node import Node
from ..core.parameter import ParameterRegistry
from ..core.mapping import MappingManager


class DAGView:
    """View for displaying the DAG structure."""
    
    def __init__(self, dag: DAG):
        """Initialize DAG view."""
        self.dag = dag
    
    def render(self, width: int, height: int) -> List[str]:
        """
        Render DAG view as list of strings.
        
        Args:
            width: View width in characters
            height: View height in characters
            
        Returns:
            List of strings representing the view
        """
        lines = []
        
        try:
            sorted_nodes = self.dag.topological_sort()
        except Exception:
            sorted_nodes = self.dag.nodes
        
        if not sorted_nodes:
            lines.append("(No nodes)")
        else:
            for i, node in enumerate(sorted_nodes):
                if len(lines) >= height - 1:
                    break
                
                node_type = type(node).__name__.replace("Node", "")
                status = "✓" if node.enabled else "✗"
                node_str = f"{i+1}. {status} {node.name} ({node_type})"
                if len(node_str) > width:
                    node_str = node_str[:width-3] + "..."
                lines.append(node_str)
                
                deps = self.dag.get_dependencies(node)
                if deps and len(lines) < height - 1:
                    dep_names = ", ".join(dep.name for dep in list(deps)[:3])
                    if len(deps) > 3:
                        dep_names += "..."
                    dep_str = f"   ← {dep_names}"
                    if len(dep_str) > width:
                        dep_str = dep_str[:width-3] + "..."
                    lines.append(dep_str)
        
        # Pad to requested height
        while len(lines) < height:
            lines.append("")
        
        return lines[:height]


class ParametersView:
    """View for displaying parameters."""
    
    def __init__(self):
        """Initialize parameters view."""
        self.registry = ParameterRegistry()
    
    def render(self, width: int, height: int) -> List[str]:
        """
        Render parameters view as list of strings.
        
        Args:
            width: View width in characters
            height: View height in characters
            
        Returns:
            List of strings representing the view
        """
        lines = []
        
        params = self.registry.all()
        if not params:
            lines.append("(No parameters)")
        else:
            for param_id, param in sorted(params.items()):
                if len(lines) >= height - 1:
                    break
                
                value_str = str(param.value)
                if isinstance(param.value, float):
                    value_str = f"{param.value:.3f}"
                
                # Truncate param_id if needed
                display_id = param_id
                max_id_len = width - len(value_str) - 3
                if len(display_id) > max_id_len:
                    display_id = "..." + display_id[-(max_id_len-3):]
                
                line = f"{display_id}: {value_str}"
                if len(line) > width:
                    line = line[:width-3] + "..."
                lines.append(line)
        
        # Pad to requested height
        while len(lines) < height:
            lines.append("")
        
        return lines[:height]


class MappingsView:
    """View for displaying signal-to-parameter mappings."""
    
    def __init__(self, mapping_manager: MappingManager):
        """Initialize mappings view."""
        self.mapping_manager = mapping_manager
    
    def render(self, width: int, height: int) -> List[str]:
        """
        Render mappings view as list of strings.
        
        Args:
            width: View width in characters
            height: View height in characters
            
        Returns:
            List of strings representing the view
        """
        lines = []
        
        mappings = self.mapping_manager.all()
        if not mappings:
            lines.append("(No mappings)")
        else:
            for i, mapping in enumerate(mappings):
                if len(lines) >= height - 1:
                    break
                
                source_name = type(mapping.source).__name__
                if hasattr(mapping.source, 'key'):
                    source_name = f"{source_name}({mapping.source.key})"
                elif hasattr(mapping.source, 'frequency'):
                    source_name = f"{source_name}({mapping.source.frequency:.2f}Hz)"
                
                target_id = mapping._target_id
                
                # Truncate if needed
                arrow = " → "
                max_source_len = (width - len(target_id) - len(arrow) - 3) // 2
                if len(source_name) > max_source_len:
                    source_name = source_name[:max_source_len-3] + "..."
                
                line = f"{source_name}{arrow}{target_id}"
                if len(line) > width:
                    # Truncate target instead
                    max_target_len = width - len(source_name) - len(arrow) - 3
                    target_id = "..." + target_id[-(max_target_len-3):]
                    line = f"{source_name}{arrow}{target_id}"
                
                lines.append(line)
        
        # Pad to requested height
        while len(lines) < height:
            lines.append("")
        
        return lines[:height]

