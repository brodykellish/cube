"""
DAG configuration serialization for saving and loading DAG states.

Encodes the full DAG structure including source nodes and effect chain.
"""
from pathlib import Path
from typing import Dict, List, Optional, Any
import yaml

from cube.dag.dag import DAG
from cube.dag.source_node import SourceNode
from cube.dag.effect_node import EffectNode
from cube.dag.video_source_node import VideoSourceNode
from cube.input.actions import Action


class DAGConfigEncoder:
    """Encodes a DAG into a serializable configuration."""
    
    @staticmethod
    def encode(dag: DAG, effect_manager) -> Dict[str, Any]:
        """
        Encode DAG state into a configuration dictionary.
        
        Args:
            dag: DAG instance to encode
            effect_manager: EffectManager instance to get effect action mappings
            
        Returns:
            Dictionary containing DAG configuration
        """
        config = {
            'version': '1.0',
            'sources': [],
            'effects': []
        }
        
        # Encode source nodes
        for root_node in dag.root_nodes:
            if isinstance(root_node, SourceNode):
                source_config = {
                    'type': 'shader',
                    'shader_path': str(root_node.shader_path)
                }
                config['sources'].append(source_config)
            elif isinstance(root_node, VideoSourceNode):
                # Extract video path from frame loader
                if hasattr(root_node, 'frame_loader') and hasattr(root_node.frame_loader, 'file_path'):
                    source_config = {
                        'type': 'video',
                        'video_path': str(root_node.frame_loader.file_path)
                    }
                    config['sources'].append(source_config)
        
        # Encode effect chain in topological order
        # We need to traverse the DAG to get the effect order
        effect_order = DAGConfigEncoder._get_effect_order(dag, effect_manager)
        for action in effect_order:
            effect_config = {
                'action': action.name,
                'shader_path': effect_manager._registry[action].shader_path,
                'node_class': effect_manager._registry[action].node_class,
                'priority': effect_manager._registry[action].priority
            }
            config['effects'].append(effect_config)
        
        return config
    
    @staticmethod
    def _get_effect_order(dag: DAG, effect_manager) -> List[Action]:
        """
        Get effect nodes in topological order (order they appear in the chain).
        
        Args:
            dag: DAG instance
            effect_manager: EffectManager instance
            
        Returns:
            List of Actions in the order they appear in the effect chain
        """
        # Get active effects in the order they were activated
        active_actions = effect_manager.get_active_actions()
        
        # Sort by priority and activation order to match the actual DAG structure
        # The effect manager already maintains the order, so we can use it directly
        return active_actions
    
    @staticmethod
    def save(config: Dict[str, Any], file_path: Path) -> None:
        """
        Save DAG configuration to a YAML file.
        
        Args:
            config: Configuration dictionary
            file_path: Path to save the configuration file
        """
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)


class DAGConfigDecoder:
    """Decodes a DAG configuration and rebuilds the DAG."""
    
    @staticmethod
    def load(file_path: Path) -> Dict[str, Any]:
        """
        Load DAG configuration from a YAML file.
        
        Args:
            file_path: Path to the configuration file
            
        Returns:
            Configuration dictionary
        """
        with open(file_path, 'r') as f:
            config = yaml.safe_load(f)
        return config
    
    @staticmethod
    def decode(config: Dict[str, Any], renderer, effect_manager) -> Dict[str, Any]:
        """
        Decode configuration into a pipeline deployment config.
        
        Args:
            config: Configuration dictionary
            renderer: DAGRenderer instance (for creating nodes)
            effect_manager: EffectManager instance (for effect registration)
            
        Returns:
            Pipeline configuration dictionary compatible with deploy_pipeline()
        """
        pipeline_config = {
            'source': {},
            'effects': []
        }
        
        # Decode source (assume single source for now)
        sources = config.get('sources', [])
        if sources:
            source_config = sources[0]  # Use first source
            if source_config.get('type') == 'video':
                pipeline_config['source']['video_path'] = source_config.get('video_path')
            elif source_config.get('type') == 'shader':
                pipeline_config['source']['shader_path'] = source_config.get('shader_path')
        
        # Decode effects
        effects = config.get('effects', [])
        for effect_config in effects:
            action_name = effect_config.get('action')
            if action_name:
                try:
                    action = Action[action_name]
                    pipeline_config['effects'].append({
                        'action': action_name,
                        'enabled': True
                    })
                except (KeyError, AttributeError):
                    print(f"[DAGConfig] Warning: Unknown effect action: {action_name}")
        
        return pipeline_config

