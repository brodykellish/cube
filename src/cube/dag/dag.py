"""
DAG (Directed Acyclic Graph) system for cube.

Manages nodes and their connections, provides topological sorting
for proper rendering order.
"""
from typing import List, Dict, Set, Optional
from .node import Node


class DAG:
    """
    Directed acyclic graph of nodes.
    
    Manages nodes and their dependencies, provides topological sorting
    for correct rendering order.
    """

    def __init__(self):
        """Initialize DAG."""
        self.nodes = []
        self._dependencies = {}

    def add_node(self, node: Node):
        """Add a node to the DAG."""
        if node not in self.nodes:
            self.nodes.append(node)
            self._dependencies[node] = set()

    def remove_node(self, node: Node):
        """Remove a node from the DAG."""
        if node in self.nodes:
            self.nodes.remove(node)
            if node in self._dependencies:
                del self._dependencies[node]
            for deps in self._dependencies.values():
                deps.discard(node)

    def connect(self, source: Node, target: Node):
        """
        Connect two nodes (source -> target).
        
        This establishes a dependency: target depends on source.
        """
        if source not in self.nodes:
            self.add_node(source)
        if target not in self.nodes:
            self.add_node(target)
        self._dependencies[target].add(source)

    def get_dependencies(self, node: Node) -> Set[Node]:
        """Get all nodes that this node depends on."""
        return self._dependencies.get(node, set()).copy()

    def topological_sort(self) -> List[Node]:
        """
        Return nodes in topological order (dependencies first).
        
        Uses Kahn's algorithm for topological sorting.
        
        Returns:
            List of nodes in dependency order
        """
        in_degree = {node: 0 for node in self.nodes}
        for node in self.nodes:
            for dep in self._dependencies.get(node, set()):
                in_degree[node] += 1
        
        queue = [node for node in self.nodes if in_degree[node] == 0]
        result = []
        
        while queue:
            node = queue.pop(0)
            result.append(node)
            for other_node in self.nodes:
                if node in self._dependencies.get(other_node, set()):
                    in_degree[other_node] -= 1
                    if in_degree[other_node] == 0:
                        queue.append(other_node)
        
        if len(result) != len(self.nodes):
            raise RuntimeError('Cycle detected in DAG')
        return result

    def render(self, t: float, resolution: tuple[float, float]):
        """
        Render all nodes in topological order.
        
        Args:
            t: Current time in seconds
            resolution: Resolution as (width, height)
        """
        sorted_nodes = self.topological_sort()
        for node in sorted_nodes:
            node.render(t, resolution)

    def get_final_node(self) -> Optional[Node]:
        """
        Get the final output node (node with no dependents).
        
        Returns:
            Final node or None if no such node exists
        """
        dependents = set()
        for deps in self._dependencies.values():
            dependents.update(deps)
        
        for node in self.nodes:
            if node not in dependents:
                return node
        
        return None

    def cleanup(self):
        """Clean up all nodes."""
        for node in self.nodes:
            node.cleanup()
