#!/bin/bash
# Switch to Minilab3 controller configuration

cd "$(dirname "$0")"

echo "Switching to Minilab3 configuration..."

# Check if we have .active backups (original configs)
if [ -f midi_config.yml.active ]; then
    cp midi_config.yml.active midi_config.yml
    echo "✓ Restored Minilab3 midi_config.yml"
else
    echo "⚠ No backup found, configs already at Minilab3"
fi

if [ -f effect_bindings.yml.active ]; then
    cp effect_bindings.yml.active effect_bindings.yml
    echo "✓ Restored Minilab3 effect_bindings.yml"
else
    echo "⚠ No backup found, configs already at Minilab3"
fi

echo "✓ Minilab3 configuration activated!"
echo ""
echo "Restart your cube application to apply changes."
