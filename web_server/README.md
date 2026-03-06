# Cube Web Server

Flask-based REST API server for cube visualization control.

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the server:
```bash
python run_server.py
```

The server will start on `http://127.0.0.1:5000`

## API Endpoints

### Visualization Control
- `POST /api/visualization/start` - Start visualization
- `POST /api/visualization/stop` - Stop visualization
- `GET /api/status` - Get current status

### Pipeline Management
- `POST /api/pipeline/deploy` - Deploy a DAG pipeline
  ```json
  {
    "source": {"shader_path": "shaders/effects/glitch.glsl"},
    "effects": [{"action": "TOGGLE_BULGE", "enabled": true}],
    "pixel_mapper": "surface"
  }
  ```

### Parameters
- `POST /api/parameters` - Update parameters
  ```json
  {"name": "iParam0", "value": 0.75}
  ```
  or batch:
  ```json
  {"parameters": {"iParam0": 0.5, "iParam1": 0.8}}
  ```
- `GET /api/parameters` - Get all parameter values

### Effects
- `GET /api/effects` - List all available effects
- `POST /api/effects/<action_name>/enable` - Enable an effect
- `POST /api/effects/<action_name>/disable` - Disable an effect

### Settings
- `GET /api/settings` - Get all settings
- `POST /api/settings` - Update a setting
  ```json
  {"name": "brightness", "value": 80.0}
  ```

### Resources
- `GET /api/resources/shaders` - List all shader files by directory
- `GET /api/resources/videos` - List all video files by directory

### Audio
- `GET /api/audio/stats` - Get audio signal statistics (placeholder)


