"""
DAG (Directed Acyclic Graph) system for cube.

Nodes track their own connections (doubly-linked structure).
DAG tracks root nodes and provides connection management.
"""
from typing import List, Set, Optional
from .node import Node


class DAG:
    """
    DAG that tracks root nodes and provides connection management.
    
    Nodes themselves track parent/children relationships.
    DAG maintains a list of root nodes (source nodes with no parent).
    """
    
    def __init__(self):
        self.root_nodes: List[Node] = []  # Source nodes (nodes with no parent)
        self._all_nodes: Set[Node] = set()  # All nodes for quick lookups
    
    def add_node(self, node: Node, is_root: bool = False):
        """
        Add a node to the DAG.
        
        Args:
            node: Node to add
            is_root: If True, add to root_nodes. If False and node has no parent, add to root_nodes.
        """
        if node not in self._all_nodes:
            self._all_nodes.add(node)
            if is_root or node.parent is None:
                if node not in self.root_nodes:
                    self.root_nodes.append(node)
    
    def remove_node(self, node: Node):
        """
        Remove a node and all its connections.
        
        Args:
            node: Node to remove
        """
        if node not in self._all_nodes:
            return
        
        # Disconnect from parent
        if node.parent:
            if node in node.parent.children:
                node.parent.children.remove(node)
            node.parent = None
        
        # Disconnect from children
        for child in list(node.children):
            child.parent = None
        node.children.clear()
        
        # Remove from root_nodes if present
        if node in self.root_nodes:
            self.root_nodes.remove(node)
        
        # Remove from all_nodes
        self._all_nodes.discard(node)
    
    def connect(self, parent: Node, child: Node):
        """
        Connect parent node to child node.
        
        Args:
            parent: Source node
            child: Target node
        """
        # Ensure both nodes are in the DAG
        if parent not in self._all_nodes:
            self.add_node(parent, is_root=True)
        if child not in self._all_nodes:
            self.add_node(child, is_root=False)
        
        # Disconnect child from previous parent if any
        if child.parent:
            if child in child.parent.children:
                child.parent.children.remove(child)
        
        # Connect
        child.parent = parent
        if child not in parent.children:
            parent.children.append(child)
        
        # Update root_nodes: child is no longer a root
        if child in self.root_nodes:
            self.root_nodes.remove(child)
        
        # Ensure parent is in root_nodes if it has no parent
        if parent.parent is None and parent not in self.root_nodes:
            self.root_nodes.append(parent)
    
    def disconnect(self, child: Node):
        """
        Disconnect a child node from its parent.
        
        Args:
            child: Child node to disconnect
        """
        if child.parent:
            if child in child.parent.children:
                child.parent.children.remove(child)
            child.parent = None
            
            # Child becomes a root node
            if child not in self.root_nodes:
                self.root_nodes.append(child)
    
    def swap_source(self, old_source: Node, new_source: Node):
        """
        Swap a source node, preserving all connections.
        
        Removes the old source node and adds the new one, moving all children
        from the old source to the new source. This preserves the effect chain.
        
        Args:
            old_source: Source node to remove
            new_source: Source node to add
        """
        if old_source not in self._all_nodes:
            # Old source not in DAG, just add new one
            self.add_node(new_source, is_root=True)
            return
        
        # Get children before removing old source
        children = list(old_source.children)
        
        # Remove old source (this will disconnect children)
        self.remove_node(old_source)
        
        # Add new source
        self.add_node(new_source, is_root=True)
        
        # Reconnect children to new source
        for child in children:
            self.connect(new_source, child)
    
    @property
    def nodes(self) -> List[Node]:
        """Get all nodes in the DAG."""
        return list(self._all_nodes)
    
    def topological_sort(self) -> List[Node]:
        """
        Return nodes in dependency order (breadth-first from roots).
        
        Returns:
            List of nodes in topological order
        """
        result: List[Node] = []
        visited: Set[Node] = set()
        queue: List[Node] = list(self.root_nodes)
        
        while queue:
            node = queue.pop(0)
            if node in visited:
                continue
            visited.add(node)
            result.append(node)
            
            # Add children to queue
            for child in node.children:
                if child not in visited:
                    queue.append(child)
        
        # Check for cycles (if we didn't visit all nodes, there's a cycle)
        if len(result) != len(self._all_nodes):
            raise RuntimeError('Cycle detected in DAG')
        
        return result
    
    def cleanup(self):
        """Clean up all nodes."""
        for node in list(self._all_nodes):
            node.cleanup()
        self.root_nodes.clear()
        self._all_nodes.clear()
