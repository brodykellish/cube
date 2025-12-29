TODO
===

A summary of all the things that need doing, roughly prioritized.

# Bugfixes
- fix display resizing thread issues.
- get the MIDI controller working again (might be easy)

# Features
- Add new shader effects. Current set is fine, but not optimal. Need to approach this with some dedicated planning.
- fullscreen support for the visualization window. Fix the threading issues and segfaulting.
- improved debug ui pane.
- improved menu system!
- LFOs (not essential - probably wouldn't use them)
- video / webcam input w/ a passthrough shader
- multiple source nodes in the dag, combined via mixer nodes. Probably have 4 independent source nodes, that get mixed by a mixing node and fed into single effect chain?
- expose parameters from the DAG and automatically assign them to control keybindings / midi CCs

# Refactoring
- DAG needs to be made more robust. See dag_architecture_refactor.md for the plan. Involves cleaner separation of concerns between dag.py and dag_renderer.py
- we need to improve input handling. Input source drivers should translate hardware-specific driver code into a clean unified control schema. Currently, InputManager is doing a lot of weird heavy lifting. All press/hold/release semantics should be abstracted at the driver/input source level. Also need to clean up our definition of "input source" - how do these differ from the drivers?
- display needs work. we are moving to a windowed system. abstractions are no longer relevant. need to somehow support single-window and multi-window mode (for RPi and MacOS respectively)
- **Refactor pyglet/pygame window management to be thread-safe**: Current implementation has race conditions between visualization thread and main thread during window operations (fullscreen, resize, close). Consider extending Pyglet's Window class directly to better integrate with pyglet's event system and ensure proper thread synchronization. See SEGFAULT_FIXES_SUMMARY.md for current workarounds and issues.
