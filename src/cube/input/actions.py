"""
Input actions and axes for unified input system.

Actions are discrete (press/release/hold).
Axes are continuous (0.0 to 1.0 or -1.0 to 1.0).
"""

from enum import Enum, auto


class Action(Enum):
    """
    Discrete actions (press/release/hold events).

    These represent semantic actions that can be triggered by
    any input device (keyboard, MIDI, gamepad).
    """
    # Navigation
    NAVIGATE_UP = auto()
    NAVIGATE_DOWN = auto()
    NAVIGATE_LEFT = auto()
    NAVIGATE_RIGHT = auto()
    CONFIRM = auto()
    CANCEL = auto()
    BACK = auto()

    # Settings
    TOGGLE_DEBUG = auto()
    TOGGLE_PREVIEW = auto()
    TOGGLE_INPUT_FORWARDING = auto()
    TOGGLE_VISUALIZATION_FULLSCREEN = auto()
    INCREASE_BRIGHTNESS = auto()
    DECREASE_BRIGHTNESS = auto()
    INCREASE_GAMMA = auto()
    DECREASE_GAMMA = auto()
    INCREASE_FPS = auto()
    DECREASE_FPS = auto()
    RELOAD_SHADER = auto()
    TOGGLE_AUDIO = auto()

    # Additive effects
    TOGGLE_FLASH = auto()
    TOGGLE_MATRIX = auto()
    TOGGLE_LIGHTNING = auto()
    TRIGGER_IMAGE_FLASH = auto()
    TOGGLE_MINIATURE_OVERLAY = auto()
    
    # Color effects
    TOGGLE_RGB_SPLIT = auto()
    TOGGLE_PSYCHEDELIC = auto()
    TOGGLE_INVERT = auto()
    TOGGLE_GRAYSCALE = auto()
    TOGGLE_THRESHOLD = auto()
    TOGGLE_RGB_TO_HSB = auto()
    
    # Edge detection and blur
    TOGGLE_EDGE_DETECTION = auto()
    
    # Distortion effects
    TOGGLE_BLUR = auto()
    TOGGLE_VHS = auto()
    TOGGLE_PIXELATE = auto()
    TOGGLE_KALEIDOSCOPE = auto()
    TOGGLE_SWIRL = auto()
    TOGGLE_BULGE = auto()
    TOGGLE_PINCH = auto()
    TOGGLE_SINEWAVE_DISTORT = auto()
    TOGGLE_DISPLACEMENT_MAP = auto()
    TOGGLE_SHAKE = auto()
    TOGGLE_SCANLINES = auto()
    TOGGLE_GLITCH = auto()
    TOGGLE_ASCII = auto()
    TOGGLE_MIRROR = auto()
    TOGGLE_STRIPES = auto()
    TOGGLE_FRAME_DIFFERENCING = auto()
    TOGGLE_MOSAIC = auto()
    TOGGLE_SLITSCAN = auto()
    TOGGLE_VIDEO_FEEDBACK = auto()
    TOGGLE_MONITOR = auto()

    # Parameter increment/decrement (keyboard control)
    INC_PARAM0 = auto()
    DEC_PARAM0 = auto()
    INC_PARAM1 = auto()
    DEC_PARAM1 = auto()
    INC_PARAM2 = auto()
    DEC_PARAM2 = auto()
    INC_PARAM3 = auto()
    DEC_PARAM3 = auto()
    INC_PARAM4 = auto()
    DEC_PARAM4 = auto()
    INC_PARAM5 = auto()
    DEC_PARAM5 = auto()
    INC_PARAM6 = auto()
    DEC_PARAM6 = auto()
    INC_PARAM7 = auto()
    DEC_PARAM7 = auto()
    
    # Effect undo/redo
    UNDO_EFFECT = auto()
    REDO_EFFECT = auto()


class Axis(Enum):
    """
    Continuous axes (analog values).

    Typically range from 0.0 to 1.0 (faders, parameters)
    or -1.0 to 1.0 (bidirectional like camera controls).
    """
    # Camera control
    CAMERA_PITCH = auto()   # Up/down rotation
    CAMERA_YAW = auto()     # Left/right rotation
    CAMERA_ROLL = auto()    # Barrel roll
    CAMERA_ZOOM = auto()    # Distance from origin

    # Shader parameters
    PARAM0 = auto()
    PARAM1 = auto()
    PARAM2 = auto()
    PARAM3 = auto()
    PARAM4 = auto()
    PARAM5 = auto()
    PARAM6 = auto()
    PARAM7 = auto()

    SEED = auto()  # Random seed from chord/notes

    # Envelope editor (modal overlay)
    ENVELOPE_ATTACK = auto()
    ENVELOPE_DECAY = auto()
    ENVELOPE_SUSTAIN = auto()
    ENVELOPE_RELEASE = auto()
    ENVELOPE_WIDTH = auto()


class InputContext(Enum):
    """
    Input contexts with different binding sets.

    Switching context changes which bindings are active.
    """
    MENU = auto()
    VISUALIZATION = auto()
    PROMPT = auto()


class ActionState(Enum):
    """State of an action within a frame"""
    PRESSED = auto()   # Pressed this frame
    HELD = auto()      # Held down
    RELEASED = auto()  # Released this frame
