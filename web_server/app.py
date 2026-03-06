"""
Flask web server for cube visualization API.

Provides REST API endpoints for:
- Visualization lifecycle (start/stop)
- Parameter updates
- Effect management
- Pipeline deployment
- Settings management
- Resource discovery (shaders, videos, effects)
"""
import os
import sys
from pathlib import Path
from flask import Flask, jsonify, request
from flask_cors import CORS
from typing import Dict, Any, Optional
import yaml

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cube.api.visualization_api import VisualizationAPI, VisualizationStatus
from cube.midi.midi_state import MIDIState
from cube.midi.usb_driver import USBMIDIDriver
from cube.midi.config_loader import load_midi_config
from cube.render.effect_config_loader import load_effect_config
from cube.services import ConfigurationService, EffectRegistry, ParameterSourceManager


def create_app(api: Optional[VisualizationAPI] = None) -> Flask:
    """
    Create and configure Flask application.
    
    Args:
        api: Optional VisualizationAPI instance (created if not provided)
    
    Returns:
        Configured Flask app
    """
    app = Flask(__name__)
    CORS(app)  # Enable CORS for frontend
    
    # Initialize API if not provided
    if api is None:
        # Find project root
        project_root = Path(__file__).parent.parent
        
        # Initialize MIDI
        midi_state = MIDIState(num_channels=8)
        midi_config = load_midi_config()
        usb_midi = None
        try:
            usb_midi = USBMIDIDriver(midi_state, midi_config)
        except Exception:
            pass  # USB MIDI optional
        
        # Create API
        api = VisualizationAPI(
            width=64,
            height=64,
            num_panels=6,
            scale=1,
            midi_state=midi_state,
            usb_midi=usb_midi,
        )
    
    # Store API in app context
    app.config['viz_api'] = api
    app.config['project_root'] = Path(__file__).parent.parent

    # Initialize services
    project_root = Path(__file__).parent.parent
    app.config['config_service'] = ConfigurationService(project_root / 'dag_configs')
    app.config['effect_registry'] = EffectRegistry(
        project_root / 'effects_config.yml',
        project_root / 'effect_bindings.yml'
    )
    app.config['param_source_manager'] = ParameterSourceManager()

    # Register routes
    register_routes(app)

    return app


def register_routes(app: Flask):
    """Register all API routes."""
    
    @app.route('/api/health', methods=['GET'])
    def health():
        """Health check endpoint."""
        return jsonify({'status': 'ok'})
    
    @app.route('/api/status', methods=['GET'])
    def get_status():
        """Get visualization status."""
        api = app.config['viz_api']
        return jsonify(api.get_status_info())
    
    @app.route('/api/visualization/start', methods=['POST'])
    def start_visualization():
        """Start the visualization system."""
        api = app.config['viz_api']
        success = api.start()
        if success:
            return jsonify({'success': True, 'status': api.status.value})
        return jsonify({'success': False, 'error': 'Failed to start visualization'}), 500
    
    @app.route('/api/visualization/stop', methods=['POST'])
    def stop_visualization():
        """Stop the visualization system."""
        api = app.config['viz_api']
        success = api.stop()
        if success:
            return jsonify({'success': True, 'status': api.status.value})
        return jsonify({'success': False, 'error': 'Failed to stop visualization'}), 500
    
    @app.route('/api/pipeline/deploy', methods=['POST'])
    def deploy_pipeline():
        """Deploy a DAG pipeline."""
        api = app.config['viz_api']
        data = request.get_json()
        
        source = data.get('source')
        effects = data.get('effects', [])
        pixel_mapper = data.get('pixel_mapper', 'surface')
        
        success = api.deploy_pipeline(
            source=source,
            effects=effects,
            pixel_mapper=pixel_mapper
        )
        
        if success:
            return jsonify({'success': True})
        return jsonify({'success': False, 'error': 'Failed to deploy pipeline'}), 500
    
    @app.route('/api/parameters', methods=['POST'])
    def set_parameters():
        """Update one or more parameters."""
        api = app.config['viz_api']
        data = request.get_json()
        
        if 'name' in data and 'value' in data:
            # Single parameter
            success = api.set_parameter(data['name'], data['value'])
        elif 'parameters' in data:
            # Batch update
            success = api.set_parameters(data['parameters'])
        else:
            return jsonify({'success': False, 'error': 'Invalid request format'}), 400
        
        if success:
            return jsonify({'success': True})
        return jsonify({'success': False, 'error': 'Failed to set parameter'}), 500
    
    @app.route('/api/parameters', methods=['GET'])
    def get_parameters():
        """Get all current parameter values."""
        api = app.config['viz_api']
        status_info = api.get_status_info()
        parameters = status_info.get('parameters', {})
        return jsonify(parameters)
    
    @app.route('/api/effects', methods=['GET'])
    def get_effects():
        """Get list of available effects."""
        project_root = app.config['project_root']
        config_path = project_root / 'effects_config.yml'
        effects = load_effect_config(config_path)
        
        effect_list = []
        for effect in effects:
            effect_list.append({
                'action': effect.action.name,
                'shader': str(effect.shader_path),
                'node_class': effect.node_class,
                'trigger_mode': effect.trigger_mode.value,
                'priority': effect.priority,
            })
        
        return jsonify(effect_list)
    
    @app.route('/api/effects/<action_name>/enable', methods=['POST'])
    def enable_effect(action_name: str):
        """Enable an effect."""
        api = app.config['viz_api']
        success = api.enable_effect(action_name)
        if success:
            return jsonify({'success': True})
        return jsonify({'success': False, 'error': f'Failed to enable effect: {action_name}'}), 500
    
    @app.route('/api/effects/<action_name>/disable', methods=['POST'])
    def disable_effect(action_name: str):
        """Disable an effect."""
        api = app.config['viz_api']
        success = api.disable_effect(action_name)
        if success:
            return jsonify({'success': True})
        return jsonify({'success': False, 'error': f'Failed to disable effect: {action_name}'}), 500
    
    @app.route('/api/settings', methods=['GET'])
    def get_settings():
        """Get all visualization settings."""
        api = app.config['viz_api']
        return jsonify(api.get_settings())
    
    @app.route('/api/settings', methods=['POST'])
    def set_setting():
        """Update a visualization setting."""
        api = app.config['viz_api']
        data = request.get_json()
        
        name = data.get('name')
        value = data.get('value')
        
        if not name or value is None:
            return jsonify({'success': False, 'error': 'Missing name or value'}), 400
        
        success = api.set_setting(name, value)
        if success:
            return jsonify({'success': True})
        return jsonify({'success': False, 'error': f'Failed to set setting: {name}'}), 500
    
    @app.route('/api/resources/shaders', methods=['GET'])
    def get_shaders():
        """Get list of available shader files organized by directory."""
        project_root = app.config['project_root']
        shaders_dir = project_root / 'shaders'
        
        shaders = {}
        if shaders_dir.exists():
            for subdir in shaders_dir.iterdir():
                if subdir.is_dir():
                    shader_files = []
                    for glsl_file in sorted(subdir.glob('*.glsl')):
                        shader_files.append({
                            'name': glsl_file.stem,
                            'path': str(glsl_file.relative_to(project_root)),
                            'full_path': str(glsl_file),
                        })
                    if shader_files:
                        shaders[subdir.name] = shader_files
        
        return jsonify(shaders)
    
    @app.route('/api/resources/videos', methods=['GET'])
    def get_videos():
        """Get list of available video files organized by directory."""
        project_root = app.config['project_root']
        videos_dir = project_root / 'videos'
        
        videos = {}
        if videos_dir.exists():
            for subdir in videos_dir.iterdir():
                if subdir.is_dir():
                    video_files = []
                    video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.webm', '.m4v']
                    for ext in video_extensions:
                        for video_file in sorted(subdir.glob(f'*{ext}')):
                            video_files.append({
                                'name': video_file.stem,
                                'path': str(video_file.relative_to(project_root)),
                                'full_path': str(video_file),
                            })
                    if video_files:
                        videos[subdir.name] = video_files
        
        return jsonify(videos)
    
    @app.route('/api/audio/stats', methods=['GET'])
    def get_audio_stats():
        """Get audio signal statistics."""
        # TODO: Implement audio stats endpoint
        # This will need to read from the audio input process
        return jsonify({
            'available': False,
            'message': 'Audio stats not yet implemented'
        })

    # ========================================================================
    # Configuration Management Endpoints
    # ========================================================================

    @app.route('/api/configs', methods=['GET'])
    def list_configs():
        """List all available configuration presets."""
        config_service = app.config['config_service']
        tag_filter = request.args.get('tag')

        try:
            configs = config_service.list_configs(tag_filter=tag_filter)
            return jsonify({
                'success': True,
                'configs': [c.to_dict() for c in configs]
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/configs/<filename>', methods=['GET'])
    def get_config(filename):
        """Get a specific configuration."""
        config_service = app.config['config_service']

        try:
            config = config_service.load_config(filename)
            return jsonify({
                'success': True,
                'config': config
            })
        except FileNotFoundError:
            return jsonify({'success': False, 'error': 'Config not found'}), 404
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/configs', methods=['POST'])
    def save_config():
        """Save current DAG configuration as a preset."""
        config_service = app.config['config_service']
        api = app.config['viz_api']
        data = request.get_json()

        filename = data.get('filename')
        metadata = data.get('metadata', {})

        if not filename:
            return jsonify({'success': False, 'error': 'Missing filename'}), 400

        try:
            # Get current DAG and effect manager from API
            # This requires accessing internal viz runner state
            # For now, return not implemented
            return jsonify({
                'success': False,
                'error': 'Saving from API not yet implemented - use menu to save'
            }), 501
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/configs/<filename>/deploy', methods=['POST'])
    def deploy_config(filename):
        """Load and deploy a configuration preset."""
        config_service = app.config['config_service']
        api = app.config['viz_api']

        try:
            # Load config
            config = config_service.load_config(filename)

            # Deploy via API (already has this functionality)
            # Extract pipeline config from DAG config
            pipeline_config = {
                'sources': config.get('sources', []),
                'effects': config.get('effects', [])
            }

            success = api.deploy_pipeline(pipeline_config)

            if success:
                return jsonify({'success': True})
            return jsonify({'success': False, 'error': 'Failed to deploy pipeline'}), 500

        except FileNotFoundError:
            return jsonify({'success': False, 'error': 'Config not found'}), 404
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/configs/<filename>', methods=['DELETE'])
    def delete_config(filename):
        """Delete a configuration preset."""
        config_service = app.config['config_service']

        try:
            success = config_service.delete_config(filename)
            if success:
                return jsonify({'success': True})
            return jsonify({'success': False, 'error': 'Config not found'}), 404
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/configs/<filename>/validate', methods=['GET'])
    def validate_config(filename):
        """Validate a configuration file."""
        config_service = app.config['config_service']

        try:
            result = config_service.validate_config(filename)
            return jsonify({
                'success': True,
                'validation': result
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    # ========================================================================
    # Effect Registry Endpoints
    # ========================================================================

    @app.route('/api/effects/registry', methods=['GET'])
    def get_effects_registry():
        """Get all effects from registry with current state."""
        effect_registry = app.config['effect_registry']

        try:
            effects = effect_registry.get_all_effects()
            return jsonify({
                'success': True,
                'effects': [e.to_dict() for e in effects]
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/effects/registry/<action_name>', methods=['GET'])
    def get_effect_by_action(action_name):
        """Get a specific effect by action name."""
        effect_registry = app.config['effect_registry']

        try:
            effect = effect_registry.get_effect_by_name(action_name)
            if effect:
                return jsonify({
                    'success': True,
                    'effect': effect.to_dict()
                })
            return jsonify({'success': False, 'error': 'Effect not found'}), 404
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/effects/registry/active', methods=['GET'])
    def get_active_effects_registry():
        """Get currently active effects."""
        effect_registry = app.config['effect_registry']

        try:
            effects = effect_registry.get_active_effects()
            return jsonify({
                'success': True,
                'effects': [e.to_dict() for e in effects]
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/effects/registry/search', methods=['GET'])
    def search_effects():
        """Search effects by name or shader path."""
        effect_registry = app.config['effect_registry']
        query = request.args.get('q', '')

        if not query:
            return jsonify({'success': False, 'error': 'Missing search query'}), 400

        try:
            effects = effect_registry.search_effects(query)
            return jsonify({
                'success': True,
                'effects': [e.to_dict() for e in effects]
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/effects/registry/categories', methods=['GET'])
    def get_effect_categories():
        """Get effects grouped by category."""
        effect_registry = app.config['effect_registry']

        try:
            categories = effect_registry.get_effect_categories()
            result = {}
            for category, effects in categories.items():
                result[category] = [e.to_dict() for e in effects]

            return jsonify({
                'success': True,
                'categories': result
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    # ========================================================================
    # Parameter Source Manager Endpoints
    # ========================================================================

    @app.route('/api/parameters/sources', methods=['GET'])
    def get_parameter_sources():
        """Get source information for all parameters."""
        param_source_manager = app.config['param_source_manager']

        try:
            sources = param_source_manager.get_all_sources()
            result = {param_id: info.to_dict() for param_id, info in sources.items()}

            return jsonify({
                'success': True,
                'sources': result
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/parameters/<param_id>/source', methods=['GET'])
    def get_parameter_source(param_id):
        """Get source information for a specific parameter."""
        param_source_manager = app.config['param_source_manager']

        try:
            info = param_source_manager.get_parameter_info(param_id)
            if info:
                return jsonify({
                    'success': True,
                    'source': info.to_dict()
                })
            return jsonify({'success': False, 'error': 'Parameter not found'}), 404
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/parameters/<param_id>/lock', methods=['POST'])
    def lock_parameter(param_id):
        """Lock a parameter to a specific source."""
        param_source_manager = app.config['param_source_manager']
        data = request.get_json()

        source_str = data.get('source')
        if not source_str:
            return jsonify({'success': False, 'error': 'Missing source'}), 400

        try:
            from cube.services import ParameterSource
            source = ParameterSource[source_str.upper()]
            param_source_manager.lock_parameter(param_id, source)

            return jsonify({'success': True})
        except KeyError:
            return jsonify({'success': False, 'error': f'Invalid source: {source_str}'}), 400
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/parameters/<param_id>/unlock', methods=['POST'])
    def unlock_parameter(param_id):
        """Unlock a parameter."""
        param_source_manager = app.config['param_source_manager']

        try:
            param_source_manager.unlock_parameter(param_id)
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/parameters/conflicts', methods=['GET'])
    def get_parameter_conflicts():
        """Detect parameter control conflicts."""
        param_source_manager = app.config['param_source_manager']

        try:
            conflicts = param_source_manager.detect_conflicts()
            return jsonify({
                'success': True,
                'conflicts': conflicts
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500


if __name__ == '__main__':
    app = create_app()
    app.run(host='127.0.0.1', port=5000, debug=True)

