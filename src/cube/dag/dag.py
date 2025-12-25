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

    def print_node_tree(self, node, prefix="", is_last=True, visited_nodes=None):
        """Recursively print node tree with ASCII art."""
        if visited_nodes is None:
            visited_nodes = set()
        
        if node in visited_nodes:
            print(f"{prefix}└─ {node.name} (CYCLE DETECTED)")
            return
        
        visited_nodes.add(node)
        
        connector = "└─ " if is_last else "├─ "
        status = "✓" if getattr(node, 'enabled', True) else "✗"
        node_type = type(node).__name__
        print(f"{prefix}{connector}{status} {node.name} ({node_type})")
        
        # Get dependents (nodes that depend on this one)
        dependents = []
        for other_node in self.nodes:
            if node in self._dependencies.get(other_node, set()):
                dependents.append(other_node)
        
        if dependents:
            new_prefix = prefix + ("   " if is_last else "│  ")
            for i, dep in enumerate(sorted(dependents, key=lambda n: n.name)):
                is_last_dep = (i == len(dependents) - 1)
                self.print_node_tree(dep, new_prefix, is_last_dep, visited_nodes.copy())
        
    def print_structure(self):
        """
        Print a visual representation of the DAG structure showing:
        - All nodes and their status
        - Dependency connections
        - Dependency chains
        - Topological sort order
        """
        if not self.nodes:
            print("DAG is empty (no nodes)")
            return

        print("\n" + "=" * 80)
        print("DAG STRUCTURE")
        print("=" * 80)

        # Get nodes with no dependencies (roots)
        roots = [node for node in self.nodes if not self._dependencies.get(node, set())]
        
        # Get nodes with no dependents (leaves)
        all_dependents = set()
        for deps in self._dependencies.values():
            all_dependents.update(deps)
        leaves = [node for node in self.nodes if node not in all_dependents]

        print(f"\nTotal nodes: {len(self.nodes)}")
        print(f"Root nodes (no dependencies): {len(roots)}")
        print(f"Leaf nodes (no dependents): {len(leaves)}")

        # Print dependency chains (tree view)
        print("\n" + "-" * 80)
        print("DEPENDENCY CHAINS (Tree View)")
        print("-" * 80)
        
        # Print from root nodes
        if roots:
            for i, root in enumerate(sorted(roots, key=lambda n: n.name)):
                is_last_root = (i == len(roots) - 1)
                self.print_node_tree(root, "", is_last_root)
        else:
            # If no clear roots, print all nodes (might indicate cycles or disconnected graph)
            print("(No clear root nodes - printing all nodes)")
            for i, node in enumerate(self.nodes):
                is_last = (i == len(self.nodes) - 1)
                self.print_node_tree(node, "", is_last)

        # Print topological sort order
        print("\n" + "-" * 80)
        print("TOPOLOGICAL SORT ORDER (Rendering Order)")
        print("-" * 80)
        try:
            sorted_nodes = self.topological_sort()
            for i, node in enumerate(sorted_nodes):
                status = "✓" if getattr(node, 'enabled', True) else "✗"
                node_type = type(node).__name__
                deps = self._dependencies.get(node, set())
                deps_str = ", ".join(d.name for d in sorted(deps, key=lambda n: n.name)) if deps else "none"
                print(f"  {i+1}. {status} {node.name} ({node_type}) [depends on: {deps_str}]")
        except RuntimeError as e:
            print(f"  ERROR: {e}")
            print("  (Cannot determine sort order due to cycle)")

        print("\n" + "=" * 80 + "\n")
