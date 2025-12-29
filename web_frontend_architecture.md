# Web Frontend Architecture Design

## Overview

This document outlines the architecture for a web-based DAG configuration builder and deployment system. The frontend provides a React-based UI for constructing DAG configurations (sources and effects), which are then deployed to the visualization system via a Flask backend API. The core visualization windows and rendering stack remain completely unchanged - this system integrates exclusively at the pipeline deployment layer.

## Architecture Principles

1. **DAG Configuration Focus**: Frontend is a DAG configuration builder/editor, not a menu replacement
2. **Deployment Integration**: Integration point is `VisualizationRunner.deploy_pipeline()` - no menu system integration
3. **Minimal Changes**: Core rendering, visualization windows, and DAG system remain untouched
4. **Local-First**: Designed for local deployment (Flask runs on localhost), with future cloud deployment in mind
5. **Configuration-Driven**: Users build complete DAG configs in the UI, then deploy them as a unit

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│              React Frontend (Vite) - DAG Builder              │
│  - React + TypeScript                                        │
│  - Tailwind CSS + CSS Modules                                │
│  - DAG Configuration Editor                                   │
│  - Source Selection (Shader/Video)                           │
│  - Effect Chain Builder                                       │
│  - Configuration Save/Load                                    │
└──────────────────────┬──────────────────────────────────────┘
                       │ HTTP/REST API
                       │ POST /api/pipeline/deploy
                       │ (DAG Config → Pipeline Deployment)
┌──────────────────────▼──────────────────────────────────────┐
│              Flask Backend (Local Server)                   │
│  ┌──────────────────────────────────────────────────────┐  │
│  │         API Layer (Flask Routes)                      │  │
│  │  - DAG Config Deployment                              │  │
│  │  - Pipeline Status                                     │  │
│  │  - Config File Management                             │  │
│  │  - Available Resources (shaders, videos, effects)      │  │
│  └──────────────┬─────────────────────────────────────────┘  │
│                 │                                              │
│  ┌──────────────▼─────────────────────────────────────────┐  │
│  │      Deployment Service                                │  │
│  │  - Converts DAG config to pipeline config             │  │
│  │  - Manages VisualizationRunner                        │  │
│  │  - Handles controller lifecycle                       │  │
│  └──────────────┬─────────────────────────────────────────┘  │
└─────────────────┼─────────────────────────────────────────────┘
                  │
                  │ deploy_pipeline(config)
                  │
┌─────────────────▼─────────────────────────────────────────────┐
│         Existing Cube System (Unchanged)                     │
│  - VisualizationRunner.deploy_pipeline()                     │
│  - DAGRenderer                                               │
│  - DAG System                                                │
│  - Rendering Stack                                           │
│  - Visualization Windows (OpenGL)                            │
│                                                              │
│  Note: Menu system remains separate and unchanged            │
└──────────────────────────────────────────────────────────────┘
```

## Backend Design

### Flask Application Structure

```
backend/
├── app.py                 # Flask app initialization
├── routes/
│   ├── __init__.py
│   ├── pipeline.py        # Pipeline deployment endpoints
│   ├── config.py          # DAG config file management
│   └── resources.py       # Available shaders, videos, effects
├── services/
│   ├── __init__.py
│   ├── deployment_service.py  # Manages VisualizationRunner
│   └── config_service.py      # DAG config file operations
└── models/
    ├── __init__.py
    └── schemas.py         # Request/response models
```

### Deployment Service

The `DeploymentService` manages the `VisualizationRunner` and handles DAG config deployment:

```python
class DeploymentService:
    """Service for deploying DAG configurations to VisualizationRunner."""
    
    def __init__(self):
        self.controller: Optional[CubeController] = None
        self._lock = threading.Lock()
    
    def initialize_controller(self, **kwargs) -> bool:
        """Initialize the CubeController with given parameters."""
        # Creates controller and starts visualization runner if needed
    
    def deploy_dag_config(self, dag_config: Dict[str, Any]) -> bool:
        """
        Deploy a DAG configuration.
        
        Converts DAG config format to pipeline config format and deploys.
        
        Args:
            dag_config: DAG configuration dict with 'sources' and 'effects'
        
        Returns:
            True if deployment successful, False otherwise
        """
        # Convert DAG config to pipeline config
        pipeline_config = self._dag_config_to_pipeline_config(dag_config)
        
        # Ensure visualization runner exists
        if not self.controller.visualization_runner:
            self._ensure_visualization_runner()
        
        # Deploy via VisualizationRunner
        self.controller.visualization_runner.deploy_pipeline(pipeline_config)
        return True
    
    def _dag_config_to_pipeline_config(self, dag_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert DAG config format to pipeline config format.
        
        DAG config format:
        {
            'sources': [{'type': 'shader', 'shader_path': '...'}],
            'effects': [{'action': 'EFFECT_NAME', ...}]
        }
        
        Pipeline config format:
        {
            'source': {'shader_path': '...', 'pixel_mapper': 'surface'},
            'effects': [{'action': 'EFFECT_NAME', 'enabled': True}]
        }
        """
        pipeline_config = {
            'source': {},
            'effects': []
        }
        
        # Convert source (assume single source for now)
        sources = dag_config.get('sources', [])
        if sources:
            source = sources[0]
            if source.get('type') == 'shader':
                pipeline_config['source']['shader_path'] = source.get('shader_path')
            elif source.get('type') == 'video':
                pipeline_config['source']['video_path'] = source.get('video_path')
            # Pixel mapper from config or default
            pipeline_config['source']['pixel_mapper'] = source.get('pixel_mapper', 'surface')
        
        # Convert effects
        for effect in dag_config.get('effects', []):
            pipeline_config['effects'].append({
                'action': effect.get('action'),
                'enabled': effect.get('enabled', True)
            })
        
        return pipeline_config
    
    def get_pipeline_status(self) -> Dict[str, Any]:
        """Get current pipeline status."""
        if not self.controller or not self.controller.visualization_runner:
            return {'status': 'stopped'}
        
        return {
            'status': 'running' if self.controller.visualization_runner._thread else 'stopped',
            'fps': self.controller.visualization_runner._fps_current
        }
    
    def stop_pipeline(self) -> bool:
        """Stop current visualization."""
        if self.controller and self.controller.visualization_runner:
            self.controller._cleanup_visualization()
            return True
        return False
    
    def cleanup(self):
        """Cleanup resources."""
        if self.controller:
            self.controller.cleanup()
```

### API Endpoints

#### Pipeline Deployment

```
POST /api/pipeline/deploy
     Body: {
       "sources": [
         {
           "type": "shader" | "video",
           "shader_path": "/path/to/shader.glsl" (if type=shader),
           "video_path": "/path/to/video.mp4" (if type=video),
           "pixel_mapper": "surface" | "cube"
         }
       ],
       "effects": [
         {
           "action": "EFFECT_NAME",
           "enabled": true
         }
       ]
     }
     Deploy a DAG configuration to the visualization system

GET  /api/pipeline/status
     Returns current pipeline status (running, stopped, error, fps)

POST /api/pipeline/stop
     Stop current visualization
```

#### Configuration File Management

```
GET  /api/config/list
     List all saved DAG configuration files in dag_configs/

GET  /api/config/<filename>
     Get a specific DAG configuration file content

POST /api/config/save
     Body: {
       "filename": "my_config.yaml",
       "config": {
         "sources": [...],
         "effects": [...]
       }
     }
     Save a DAG configuration to a file

DELETE /api/config/<filename>
     Delete a saved DAG configuration file
```

#### Available Resources

```
GET  /api/resources/shaders
     List available shader files (by category: effects, graphics, primitives, etc.)

GET  /api/resources/videos
     List available video files (by directory)

GET  /api/resources/effects
     List available effect actions and their metadata
     Returns effect definitions from effects_config.yml
```

### Request/Response Models

```python
# Request Models
class DAGSourceConfig(BaseModel):
    type: Literal["shader", "video"]
    shader_path: Optional[str] = None
    video_path: Optional[str] = None
    pixel_mapper: Literal["surface", "cube"] = "surface"

class DAGEffectConfig(BaseModel):
    action: str
    enabled: bool = True

class DeployPipelineRequest(BaseModel):
    """DAG configuration format matching DAGConfigEncoder/Decoder."""
    sources: List[DAGSourceConfig]
    effects: List[DAGEffectConfig] = []

class SaveConfigRequest(BaseModel):
    filename: str
    config: Dict[str, Any]  # DAG config structure

# Response Models
class PipelineStatusResponse(BaseModel):
    status: Literal["running", "stopped", "error"]
    fps: Optional[float] = None
    current_config: Optional[Dict[str, Any]] = None

class ConfigFileInfo(BaseModel):
    filename: str
    path: str
    modified: str

class ConfigListResponse(BaseModel):
    configs: List[ConfigFileInfo]

class ShaderInfo(BaseModel):
    path: str
    name: str
    category: str

class EffectInfo(BaseModel):
    action: str
    name: str
    shader_path: str
    trigger_mode: str

class ResourcesResponse(BaseModel):
    shaders: List[ShaderInfo]
    videos: List[str]
    effects: List[EffectInfo]

class ErrorResponse(BaseModel):
    error: str
    details: Optional[str] = None
```

## Frontend Design

### React Application Structure

```
frontend/
├── public/
├── src/
│   ├── main.tsx
│   ├── App.tsx
│   ├── api/
│   │   ├── client.ts          # Axios/fetch client setup
│   │   ├── pipeline.ts        # Pipeline deployment API calls
│   │   ├── config.ts          # Config file management API calls
│   │   └── resources.ts       # Available resources API calls
│   ├── components/
│   │   ├── layout/
│   │   │   ├── Layout.tsx
│   │   │   ├── Sidebar.tsx
│   │   │   └── Header.tsx
│   │   ├── dag-builder/
│   │   │   ├── DAGBuilder.tsx      # Main DAG construction UI
│   │   │   ├── SourcePanel.tsx     # Source selection/configuration
│   │   │   ├── SourceSelector.tsx  # Shader/video picker
│   │   │   ├── EffectChain.tsx      # Effect chain builder
│   │   │   ├── EffectSelector.tsx  # Effect picker
│   │   │   └── DeployButton.tsx     # Deploy action
│   │   ├── config-manager/
│   │   │   ├── ConfigManager.tsx   # Config file browser
│   │   │   ├── ConfigList.tsx      # List of saved configs
│   │   │   ├── ConfigEditor.tsx    # Config editor/viewer
│   │   │   └── SaveDialog.tsx      # Save config dialog
│   │   ├── status/
│   │   │   ├── PipelineStatus.tsx  # Current pipeline status
│   │   │   └── StatusIndicator.tsx # Running/stopped indicator
│   │   └── common/
│   │       ├── Button.tsx
│   │       ├── Input.tsx
│   │       └── Select.tsx
│   ├── hooks/
│   │   ├── usePipeline.ts      # Pipeline deployment hook
│   │   ├── useDAGConfig.ts     # DAG config state management
│   │   ├── useResources.ts     # Available resources hook
│   │   └── useConfigFiles.ts   # Config file management hook
│   ├── stores/
│   │   └── dagStore.ts         # Global DAG config state (Zustand/Context)
│   ├── types/
│   │   ├── api.ts              # API type definitions
│   │   ├── dag.ts              # DAG config types
│   │   └── pipeline.ts         # Pipeline types
│   └── styles/
│       ├── globals.css
│       └── components/
│           └── *.module.css
├── tailwind.config.js
├── vite.config.ts
└── package.json
```

### Key Frontend Components

#### DAGBuilder Component
- Main workspace for constructing DAG configurations
- Split view: Source panel + Effect chain panel
- Real-time validation and preview
- Deploy button that sends complete config to backend

#### SourcePanel Component
- Source type selection (shader vs video)
- Shader/video file browser
- Pixel mapper selection (surface/cube)
- Source configuration display

#### EffectChain Component
- Visual effect chain builder
- Drag-and-drop effect ordering (future)
- Enable/disable individual effects
- Effect metadata display

#### ConfigManager Component
- Browse saved DAG config files
- Load config into builder
- Save current config to file
- Delete config files

#### PipelineStatus Component
- Current pipeline status (running/stopped)
- FPS display
- Stop button
- Current config summary

### State Management

Use Zustand or React Context for global DAG config state:

```typescript
interface DAGConfigState {
  // Current DAG configuration being built
  sources: DAGSourceConfig[];
  effects: DAGEffectConfig[];
  
  // Available resources
  availableShaders: ShaderInfo[];
  availableVideos: string[];
  availableEffects: EffectInfo[];
  
  // Pipeline status
  pipelineStatus: PipelineStatus;
  
  // Actions
  addSource: (source: DAGSourceConfig) => void;
  removeSource: (index: number) => void;
  updateSource: (index: number, source: Partial<DAGSourceConfig>) => void;
  addEffect: (effect: DAGEffectConfig) => void;
  removeEffect: (index: number) => void;
  reorderEffects: (from: number, to: number) => void;
  loadConfig: (config: DAGConfig) => void;
  clearConfig: () => void;
  deploy: () => Promise<void>;
  loadFromFile: (filename: string) => Promise<void>;
  saveToFile: (filename: string) => Promise<void>;
}
```

## Integration Points

### 1. Controller Initialization

The Flask app needs to initialize a `CubeController` instance. This should be done:
- On first deployment request (lazy initialization)
- Controller runs in main thread (required for macOS OpenGL)

```python
# In deployment_service.py
def initialize_controller(self, **kwargs):
    with self._lock:
        if self.controller is not None:
            return True
        
        try:
            self.controller = CubeController(
                width=kwargs.get('width', 64),
                height=kwargs.get('height', 64),
                num_panels=kwargs.get('num_panels', 6),
                fps=kwargs.get('fps', 60),
                default_brightness=kwargs.get('brightness', 80.0),
                default_gamma=kwargs.get('gamma', 1.0),
                scale=kwargs.get('scale', 1),
            )
            
            # Start controller in background thread
            # Note: Visualization window must be created on main thread
            # This requires careful threading setup
            return True
        except Exception as e:
            logger.error(f"Failed to initialize controller: {e}")
            return False
```

### 2. DAG Config to Pipeline Config Conversion

Convert DAG config format (from frontend) to pipeline config format (for VisualizationRunner):

```python
def _dag_config_to_pipeline_config(self, dag_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert DAG config format to pipeline config format.
    
    DAG Config (from frontend):
    {
        "sources": [
            {
                "type": "shader",
                "shader_path": "shaders/effects/example.glsl",
                "pixel_mapper": "surface"
            }
        ],
        "effects": [
            {
                "action": "EFFECT_PSYCHEDELIC",
                "enabled": True
            }
        ]
    }
    
    Pipeline Config (for VisualizationRunner):
    {
        "source": {
            "shader_path": "shaders/effects/example.glsl",
            "pixel_mapper": "surface"
        },
        "effects": [
            {
                "action": "EFFECT_PSYCHEDELIC",
                "enabled": True
            }
        ]
    }
    """
    pipeline_config = {
        'source': {},
        'effects': []
    }
    
    # Convert sources (assume single source for now)
    sources = dag_config.get('sources', [])
    if sources:
        source = sources[0]
        if source.get('type') == 'shader':
            pipeline_config['source']['shader_path'] = source.get('shader_path')
        elif source.get('type') == 'video':
            pipeline_config['source']['video_path'] = source.get('video_path')
        pipeline_config['source']['pixel_mapper'] = source.get('pixel_mapper', 'surface')
    
    # Convert effects
    for effect in dag_config.get('effects', []):
        pipeline_config['effects'].append({
            'action': effect.get('action'),
            'enabled': effect.get('enabled', True)
        })
    
    return pipeline_config
```

### 3. Pipeline Deployment

Deploy DAG config via VisualizationRunner:

```python
def deploy_dag_config(self, dag_config: Dict[str, Any]) -> bool:
    """Deploy a DAG configuration."""
    # Ensure controller and visualization runner exist
    if not self.controller:
        self.initialize_controller()
    
    if not self.controller.visualization_runner:
        # Create visualization runner if it doesn't exist
        # This requires creating the window on main thread
        self._ensure_visualization_runner()
    
    # Convert DAG config to pipeline config
    pipeline_config = self._dag_config_to_pipeline_config(dag_config)
    
    # Deploy via VisualizationRunner (thread-safe queue)
    self.controller.visualization_runner.deploy_pipeline(pipeline_config)
    
    return True
```

### 4. Resource Discovery

Provide available shaders, videos, and effects to frontend:

```python
def get_available_shaders(self) -> List[Dict[str, str]]:
    """Scan shaders directory and return available shaders."""
    from cube.utils.app_setup import find_project_root
    
    project_root = find_project_root()
    shaders_dir = project_root / 'shaders'
    
    shaders = []
    for category_dir in shaders_dir.iterdir():
        if category_dir.is_dir():
            for shader_file in category_dir.glob('*.glsl'):
                shaders.append({
                    'path': str(shader_file.relative_to(project_root)),
                    'name': shader_file.stem,
                    'category': category_dir.name
                })
    
    return shaders

def get_available_effects(self) -> List[Dict[str, Any]]:
    """Load effect definitions from effects_config.yml."""
    from cube.render.effect_config_loader import load_effect_config
    
    effects = load_effect_config()
    return [
        {
            'action': effect.action.name,
            'name': effect.action.name,
            'shader_path': effect.shader_path,
            'trigger_mode': effect.trigger_mode.value
        }
        for effect in effects
    ]
```

## Implementation Phases

### Phase 1: Backend Foundation (Week 1)
- [ ] Flask app setup with basic structure
- [ ] DeploymentService implementation
- [ ] Controller initialization and lifecycle management
- [ ] DAG config to pipeline config conversion
- [ ] Pipeline deployment endpoint
- [ ] Basic error handling and logging

### Phase 2: Backend Resources & Config Management (Week 2)
- [ ] Resource discovery endpoints (shaders, videos, effects)
- [ ] DAG config file management endpoints (list, get, save, delete)
- [ ] Pipeline status endpoint
- [ ] Stop pipeline endpoint
- [ ] File system integration for config storage

### Phase 3: Frontend Foundation (Week 3)
- [ ] Vite + React + TypeScript setup
- [ ] Tailwind CSS configuration
- [ ] API client setup
- [ ] Basic layout components
- [ ] DAG config state management (Zustand/Context)
- [ ] Type definitions for DAG configs

### Phase 4: Frontend DAG Builder (Week 4)
- [ ] Source selection UI (shader/video picker)
- [ ] Effect chain builder UI
- [ ] DAG config editor
- [ ] Deploy button and pipeline status display
- [ ] Config file browser and manager
- [ ] Error handling and user feedback

### Phase 5: Polish & Testing (Week 5)
- [ ] End-to-end testing (frontend → backend → visualization)
- [ ] Error handling improvements
- [ ] UI/UX refinements
- [ ] Validation and error messages
- [ ] Documentation
- [ ] Deployment scripts

## Technical Considerations

### Threading Model

The existing `CubeController` runs a main loop in the main thread. For Flask integration:

**Option A: Separate Process**
- Run Flask in a separate process
- Use inter-process communication (queue, socket, etc.)
- More isolation but more complex

**Option B: Background Thread** (Recommended)
- Run Flask in a background thread
- Controller runs in main thread or separate thread
- Use thread-safe communication (queues, locks)
- Simpler but requires careful synchronization

**Option C: Async Integration**
- Convert controller to async/await
- Use Flask with async support
- Most complex but most scalable

**Recommendation**: Option B - Run Flask in a background thread, controller in main thread. Use queues for cross-thread communication.

### CORS Configuration

Since frontend runs separately, configure CORS:

```python
from flask_cors import CORS

app = Flask(__name__)
CORS(app, resources={
    r"/api/*": {
        "origins": ["http://localhost:5173"],  # Vite dev server
        "methods": ["GET", "POST", "PUT", "PATCH", "DELETE"],
        "allow_headers": ["Content-Type"]
    }
})
```

### Error Handling

- Use consistent error response format
- Log errors server-side
- Return user-friendly error messages
- Handle controller initialization failures gracefully

### Configuration Files

All config files remain in their current locations:
- `dag_configs/` - DAG configurations
- `effect_bindings.yml` - Effect bindings
- `midi_config.yml` - MIDI configuration
- `audio_mapping.yml` - Audio mappings
- `effects_config.yml` - Effect definitions

API should read/write these files directly (with proper locking for concurrent access).

## Security Considerations (Future)

For local deployment, security is minimal. For future cloud deployment:

1. **Authentication**: Add API key or OAuth
2. **Rate Limiting**: Prevent API abuse
3. **Input Validation**: Sanitize all inputs
4. **Path Traversal Protection**: Validate file paths
5. **CORS**: Restrict to known origins

## Deployment

### Local Development

```bash
# Terminal 1: Flask backend
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
flask run --port 5000

# Terminal 2: React frontend
cd frontend
npm install
npm run dev  # Runs on http://localhost:5173
```

### Production (Future)

- Backend: Deploy Flask app to cloud (AWS, GCP, etc.)
- Frontend: Build static files, serve via CDN or nginx
- WebSocket: Use Redis pub/sub for multi-instance support

## Open Questions

1. **Controller Lifecycle**: Should controller run continuously or start/stop per request?
   - **Recommendation**: Run continuously, start on first deployment request
   - Controller must run in main thread (macOS OpenGL requirement)
   - Flask can run in background thread

2. **Threading Model**: How to run Flask alongside CubeController?
   - **Option A**: Flask in background thread, controller in main thread
   - **Option B**: Separate process for Flask (more complex IPC)
   - **Recommendation**: Option A - simpler, use queues for communication

3. **Real-time Updates**: WebSocket for live status updates?
   - **Recommendation**: Phase 2 feature, start with polling GET /api/pipeline/status

4. **Visualization Preview**: Should we stream visualization frames to frontend?
   - **Recommendation**: No, keep visualization in separate window (unchanged requirement)

5. **File Upload**: How to handle shader/video file uploads?
   - **Recommendation**: Phase 2, start with file path selection from existing filesystem

6. **Multiple Sources**: Support multiple sources in DAG?
   - **Current**: Single source supported
   - **Recommendation**: Start with single source, extend later if needed

## Success Criteria

- [ ] Frontend can construct DAG configurations (sources + effects)
- [ ] Frontend can deploy DAG configs to visualization system via API
- [ ] DAG config files can be saved and loaded
- [ ] Pipeline deployment works correctly (config → VisualizationRunner)
- [ ] Visualization windows remain unchanged and functional
- [ ] No regressions in core rendering system
- [ ] Frontend provides intuitive DAG building experience
- [ ] Available resources (shaders, videos, effects) are discoverable via API

