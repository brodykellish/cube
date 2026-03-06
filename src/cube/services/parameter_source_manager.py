"""
Parameter Source Manager.

Tracks which input source (keyboard, MIDI, web API, audio) is actively
controlling each parameter. Provides visibility and conflict resolution
for live performance use.
"""

from typing import Dict, List, Optional, Set
from dataclasses import dataclass, asdict
from enum import Enum
from datetime import datetime


class ParameterSource(Enum):
    """Parameter input sources."""
    KEYBOARD = "keyboard"
    MIDI = "midi"
    WEB_API = "web_api"
    AUDIO = "audio"
    UNKNOWN = "unknown"


@dataclass
class ParameterSourceInfo:
    """Information about a parameter's current input source."""
    parameter_id: str
    current_value: float
    active_source: ParameterSource
    last_updated: str
    is_locked: bool
    locked_to: Optional[ParameterSource]

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        d = asdict(self)
        d['active_source'] = self.active_source.value
        d['locked_to'] = self.locked_to.value if self.locked_to else None
        return d


class ParameterSourceManager:
    """
    Manager for tracking parameter input sources.

    Provides visibility into which source (keyboard, MIDI, web API, audio)
    is currently controlling each parameter. Essential for debugging parameter
    conflicts during live performance.

    Features:
    - Track active source per parameter
    - Lock parameters to specific sources
    - Query source conflicts
    - Historical source tracking
    """

    def __init__(self, parameter_store=None):
        """
        Initialize parameter source manager.

        Args:
            parameter_store: Optional ParameterStore for getting current values
        """
        self.parameter_store = parameter_store

        # Track active source per parameter
        self._active_sources: Dict[str, ParameterSource] = {}

        # Track last update time per parameter
        self._last_updated: Dict[str, datetime] = {}

        # Track locked parameters
        self._locked_params: Dict[str, ParameterSource] = {}

    def update_source(
        self,
        parameter_id: str,
        source: ParameterSource,
        value: Optional[float] = None
    ):
        """
        Record a parameter update from a specific source.

        Args:
            parameter_id: Parameter ID (e.g., 'iParam0')
            source: Input source that updated the parameter
            value: Optional new value (for logging)
        """
        # Check if parameter is locked
        if parameter_id in self._locked_params:
            locked_to = self._locked_params[parameter_id]
            if source != locked_to:
                # Ignore updates from other sources when locked
                print(f"[ParamSourceMgr] Ignoring {source.value} update to {parameter_id} "
                      f"(locked to {locked_to.value})")
                return

        # Update tracking
        self._active_sources[parameter_id] = source
        self._last_updated[parameter_id] = datetime.now()

    def get_active_source(self, parameter_id: str) -> Optional[ParameterSource]:
        """
        Get the currently active source for a parameter.

        Args:
            parameter_id: Parameter ID to query

        Returns:
            ParameterSource or None if no source has updated this parameter
        """
        return self._active_sources.get(parameter_id)

    def get_parameter_info(self, parameter_id: str) -> Optional[ParameterSourceInfo]:
        """
        Get complete information about a parameter's source status.

        Args:
            parameter_id: Parameter ID to query

        Returns:
            ParameterSourceInfo or None if parameter not found
        """
        if parameter_id not in self._active_sources:
            return None

        # Get current value from parameter store
        current_value = 0.0
        if self.parameter_store:
            param = self.parameter_store.get_parameter(parameter_id)
            if param:
                current_value = param.value

        return ParameterSourceInfo(
            parameter_id=parameter_id,
            current_value=current_value,
            active_source=self._active_sources[parameter_id],
            last_updated=self._last_updated[parameter_id].isoformat(),
            is_locked=parameter_id in self._locked_params,
            locked_to=self._locked_params.get(parameter_id)
        )

    def get_all_sources(self) -> Dict[str, ParameterSourceInfo]:
        """
        Get source information for all tracked parameters.

        Returns:
            Dictionary mapping parameter ID to ParameterSourceInfo
        """
        result = {}

        for param_id in self._active_sources:
            info = self.get_parameter_info(param_id)
            if info:
                result[param_id] = info

        return result

    def lock_parameter(self, parameter_id: str, source: ParameterSource):
        """
        Lock a parameter to a specific source.

        While locked, updates from other sources will be ignored.
        Useful for ensuring web API control isn't overridden by MIDI/audio.

        Args:
            parameter_id: Parameter to lock
            source: Source to lock to
        """
        self._locked_params[parameter_id] = source
        print(f"[ParamSourceMgr] Locked {parameter_id} to {source.value}")

    def unlock_parameter(self, parameter_id: str):
        """
        Unlock a parameter, allowing all sources to control it again.

        Args:
            parameter_id: Parameter to unlock
        """
        if parameter_id in self._locked_params:
            del self._locked_params[parameter_id]
            print(f"[ParamSourceMgr] Unlocked {parameter_id}")

    def is_parameter_locked(self, parameter_id: str) -> bool:
        """
        Check if a parameter is currently locked.

        Args:
            parameter_id: Parameter to check

        Returns:
            True if locked, False otherwise
        """
        return parameter_id in self._locked_params

    def get_locked_parameters(self) -> Dict[str, ParameterSource]:
        """
        Get all currently locked parameters.

        Returns:
            Dictionary mapping parameter ID to locked source
        """
        return dict(self._locked_params)

    def get_parameters_by_source(self, source: ParameterSource) -> List[str]:
        """
        Get all parameters currently controlled by a specific source.

        Args:
            source: Source to filter by

        Returns:
            List of parameter IDs controlled by this source
        """
        return [
            param_id for param_id, param_source in self._active_sources.items()
            if param_source == source
        ]

    def detect_conflicts(self) -> List[Dict[str, any]]:
        """
        Detect potential parameter control conflicts.

        A conflict occurs when multiple sources are trying to control
        the same parameter (based on recent activity).

        Returns:
            List of conflict dictionaries with details
        """
        conflicts = []

        # Check for recent updates from multiple sources
        # (within last 5 seconds)
        now = datetime.now()
        recent_threshold = 5.0  # seconds

        # Group parameters by how recently they were updated
        recent_updates: Dict[str, List[ParameterSource]] = {}

        for param_id, last_update in self._last_updated.items():
            time_since = (now - last_update).total_seconds()

            if time_since < recent_threshold:
                if param_id not in recent_updates:
                    recent_updates[param_id] = []
                recent_updates[param_id].append(self._active_sources[param_id])

        # This is a simplified conflict detection
        # In practice, would need to track history of sources
        # For now, just report on locked parameters that have recent activity

        for param_id in self._locked_params:
            if param_id in recent_updates:
                conflicts.append({
                    'parameter_id': param_id,
                    'locked_to': self._locked_params[param_id].value,
                    'recent_source': recent_updates[param_id][0].value,
                    'message': f"{param_id} is locked but receiving updates"
                })

        return conflicts

    def clear_history(self):
        """Clear all source tracking history."""
        self._active_sources.clear()
        self._last_updated.clear()
        print("[ParamSourceMgr] Cleared source history")

    def reset_locks(self):
        """Unlock all parameters."""
        self._locked_params.clear()
        print("[ParamSourceMgr] Reset all parameter locks")

    def __repr__(self) -> str:
        return (f"ParameterSourceManager("
                f"tracked={len(self._active_sources)}, "
                f"locked={len(self._locked_params)})")
