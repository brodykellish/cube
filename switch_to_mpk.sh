#!/bin/bash
# Switch to MPK Mini Mk II controller configuration

cd "$(dirname "$0")"

echo "Switching to MPK Mini Mk II configuration..."

# Backup current configs if they don't have .active extension
if [ ! -f midi_config.yml.active ]; then
    cp midi_config.yml midi_config.yml.active
    echo "✓ Backed up current midi_config.yml"
fi

if [ ! -f effect_bindings.yml.active ]; then
    cp effect_bindings.yml effect_bindings.yml.active
    echo "✓ Backed up current effect_bindings.yml"
fi

# Copy MPK configs to active
cp midi_config_mpk.yml midi_config.yml
cp effect_bindings_mpk.yml effect_bindings.yml

echo "✓ MPK Mini Mk II configuration activated!"
echo ""
echo "Controller mapping:"
echo "  - Knobs 1-8 (CC 1-8) → Parameters 0-7"
echo "  - Pads 1-8 → Effects 1-8 (GLITCH, BLUR, DISPLACEMENT, etc.)"
echo "  - Shift+Pads 1-8 → Effects 9-16 (PSYCHEDELIC, RGB_SPLIT, etc.)"
echo ""
echo "Restart your cube application to apply changes."
