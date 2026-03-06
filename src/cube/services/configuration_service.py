"""
Configuration Service for DAG preset management.

Provides high-level operations for saving, loading, listing, and validating
DAG configurations (presets) for live performance use.
"""

from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
import yaml

from cube.dag.dag_config import DAGConfigEncoder, DAGConfigDecoder


@dataclass
class ConfigInfo:
    """Metadata about a DAG configuration file."""
    filename: str
    name: str
    description: str
    author: str
    tags: List[str]
    created: Optional[str]
    modified: str
    source_count: int
    effect_count: int
    file_path: Path

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        d = asdict(self)
        d['file_path'] = str(d['file_path'])
        return d


class ConfigurationService:
    """
    Service for managing DAG configuration files (presets).

    Provides operations for saving, loading, listing, and validating
    configuration files. Essential for quick preset switching during
    live performance.
    """

    def __init__(self, configs_dir: Path = None):
        """
        Initialize configuration service.

        Args:
            configs_dir: Directory containing configuration files
                        (default: ./dag_configs)
        """
        if configs_dir is None:
            configs_dir = Path.cwd() / 'dag_configs'

        self.configs_dir = Path(configs_dir)
        self.configs_dir.mkdir(parents=True, exist_ok=True)

    def save_config(
        self,
        dag,
        effect_manager,
        filename: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Path:
        """
        Save DAG configuration with metadata.

        Args:
            dag: DAG instance to save
            effect_manager: EffectManager instance
            filename: Name of config file (with or without .yml/.yaml extension)
            metadata: Optional metadata (name, description, author, tags)

        Returns:
            Path to saved config file

        Raises:
            ValueError: If filename is invalid
            IOError: If file cannot be written
        """
        # Ensure filename has extension
        if not filename.endswith(('.yml', '.yaml')):
            filename = f"{filename}.yml"

        # Sanitize filename
        filename = self._sanitize_filename(filename)
        file_path = self.configs_dir / filename

        try:
            # Encode DAG to config dict
            config = DAGConfigEncoder.encode(dag, effect_manager)

            # Add metadata if provided
            if metadata:
                if 'metadata' not in config:
                    config['metadata'] = {}

                config['metadata'].update({
                    'name': metadata.get('name', filename.replace('.yml', '').replace('.yaml', '')),
                    'description': metadata.get('description', ''),
                    'author': metadata.get('author', ''),
                    'tags': metadata.get('tags', []),
                    'created': metadata.get('created', datetime.now().isoformat()),
                    'modified': datetime.now().isoformat(),
                })
            else:
                # Add minimal metadata
                config['metadata'] = {
                    'name': filename.replace('.yml', '').replace('.yaml', ''),
                    'description': '',
                    'author': '',
                    'tags': [],
                    'created': datetime.now().isoformat(),
                    'modified': datetime.now().isoformat(),
                }

            # Save to file
            DAGConfigEncoder.save(config, file_path)

            print(f"[ConfigService] Saved configuration to {file_path}")
            return file_path

        except Exception as e:
            print(f"[ConfigService] Error saving config: {e}")
            raise IOError(f"Failed to save configuration: {e}") from e

    def load_config(self, filename: str) -> Dict[str, Any]:
        """
        Load DAG configuration from file.

        Args:
            filename: Name of config file (with or without extension)

        Returns:
            Configuration dictionary

        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If config file is invalid
        """
        # Try with and without extension
        file_path = self._resolve_config_path(filename)

        if not file_path or not file_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {filename}")

        try:
            config = DAGConfigDecoder.load(file_path)
            print(f"[ConfigService] Loaded configuration from {file_path}")
            return config

        except Exception as e:
            print(f"[ConfigService] Error loading config: {e}")
            raise ValueError(f"Failed to load configuration: {e}") from e

    def list_configs(self, tag_filter: Optional[str] = None) -> List[ConfigInfo]:
        """
        List all available configuration files with metadata.

        Args:
            tag_filter: Optional tag to filter configs by

        Returns:
            List of ConfigInfo objects sorted by modified date (newest first)
        """
        configs = []

        for file_path in self.configs_dir.glob('*.y*ml'):  # Match .yml and .yaml
            try:
                config_info = self._get_config_info(file_path)

                # Apply tag filter if specified
                if tag_filter and tag_filter not in config_info.tags:
                    continue

                configs.append(config_info)

            except Exception as e:
                print(f"[ConfigService] Warning: Could not read {file_path}: {e}")
                continue

        # Sort by modified date (newest first)
        configs.sort(key=lambda c: c.modified, reverse=True)

        return configs

    def delete_config(self, filename: str) -> bool:
        """
        Delete a configuration file.

        Args:
            filename: Name of config file to delete

        Returns:
            True if deleted successfully, False otherwise
        """
        file_path = self._resolve_config_path(filename)

        if not file_path or not file_path.exists():
            print(f"[ConfigService] Config not found: {filename}")
            return False

        try:
            file_path.unlink()
            print(f"[ConfigService] Deleted configuration: {file_path}")
            return True

        except Exception as e:
            print(f"[ConfigService] Error deleting config: {e}")
            return False

    def validate_config(self, filename: str) -> Dict[str, Any]:
        """
        Validate a configuration file without loading it into DAG.

        Args:
            filename: Name of config file to validate

        Returns:
            Dictionary with validation results:
            {
                'valid': bool,
                'errors': List[str],
                'warnings': List[str],
                'info': Dict[str, Any]
            }
        """
        result = {
            'valid': False,
            'errors': [],
            'warnings': [],
            'info': {}
        }

        file_path = self._resolve_config_path(filename)

        if not file_path or not file_path.exists():
            result['errors'].append(f"Configuration file not found: {filename}")
            return result

        try:
            # Load config
            with open(file_path, 'r') as f:
                config = yaml.safe_load(f)

            # Check version
            if 'version' not in config:
                result['errors'].append("Missing 'version' field")
            elif config['version'] != '1.0':
                result['warnings'].append(f"Unknown version: {config['version']}")

            # Check sources
            if 'sources' not in config or not config['sources']:
                result['errors'].append("No sources defined")
            else:
                result['info']['source_count'] = len(config['sources'])

                # Validate source paths
                for i, source in enumerate(config['sources']):
                    if source.get('type') == 'shader':
                        shader_path = Path(source.get('shader_path', ''))
                        if not shader_path.exists():
                            result['warnings'].append(
                                f"Source {i}: shader file not found: {shader_path}"
                            )
                    elif source.get('type') == 'video':
                        video_path = Path(source.get('video_path', ''))
                        if not video_path.exists():
                            result['warnings'].append(
                                f"Source {i}: video file not found: {video_path}"
                            )

            # Check effects
            if 'effects' in config:
                result['info']['effect_count'] = len(config['effects'])

                # Validate effect shader paths
                for i, effect in enumerate(config['effects']):
                    shader_path = Path(effect.get('shader_path', ''))
                    if shader_path and not shader_path.exists():
                        result['warnings'].append(
                            f"Effect {i} ({effect.get('action', '?')}): shader not found: {shader_path}"
                        )

            # Check metadata
            if 'metadata' in config:
                result['info']['metadata'] = config['metadata']

            # If no errors, mark as valid
            if not result['errors']:
                result['valid'] = True

            return result

        except Exception as e:
            result['errors'].append(f"Failed to parse config: {e}")
            return result

    def _get_config_info(self, file_path: Path) -> ConfigInfo:
        """Extract metadata from a config file."""
        with open(file_path, 'r') as f:
            config = yaml.safe_load(f)

        # Extract metadata
        metadata = config.get('metadata', {})

        # Count sources and effects
        source_count = len(config.get('sources', []))
        effect_count = len(config.get('effects', []))

        # Get file stats
        stat = file_path.stat()
        modified = datetime.fromtimestamp(stat.st_mtime).isoformat()

        return ConfigInfo(
            filename=file_path.name,
            name=metadata.get('name', file_path.stem),
            description=metadata.get('description', ''),
            author=metadata.get('author', ''),
            tags=metadata.get('tags', []),
            created=metadata.get('created'),
            modified=modified,
            source_count=source_count,
            effect_count=effect_count,
            file_path=file_path
        )

    def _resolve_config_path(self, filename: str) -> Optional[Path]:
        """Resolve config filename to full path, trying with/without extensions."""
        # Try as-is
        path = self.configs_dir / filename
        if path.exists():
            return path

        # Try with .yml extension
        if not filename.endswith(('.yml', '.yaml')):
            path = self.configs_dir / f"{filename}.yml"
            if path.exists():
                return path

            path = self.configs_dir / f"{filename}.yaml"
            if path.exists():
                return path

        return None

    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename to prevent directory traversal."""
        # Remove path components
        filename = Path(filename).name

        # Remove potentially dangerous characters
        allowed_chars = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.')
        filename = ''.join(c if c in allowed_chars else '_' for c in filename)

        return filename
