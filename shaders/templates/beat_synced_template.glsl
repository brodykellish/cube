// Beat-Synced Shader Template
// Shows how to use iBeatTrigger with debug indicator
//
// Controls:
// - Knob 1-4: Your custom parameters
// - Knob 6-8: Beat envelope (Attack/Hold/Decay)
// - Pad 8: Tap tempo

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = (fragCoord - 0.5 * iResolution.xy) / iResolution.y;

    // Camera setup
    vec3 ro = iCameraPos;
    vec3 rd = normalize(iCameraForward + uv.x * iCameraRight + uv.y * iCameraUp);

    // Get beat trigger (0.0-1.0)
    float beat = iBeatTrigger;

    // If no tempo detected, show a dim placeholder
    if (beat == 0.0) {
        fragColor = vec4(0.1, 0.1, 0.1, 1.0);  // Dark gray
        return;
    }

    // YOUR SHADER CODE HERE
    // Use 'beat' to modulate your visuals
    // Example: float size = baseSize * (1.0 + beat * 0.5);

    vec3 color = vec3(0.0);

    // Simple example: color that pulses with beat
    color = vec3(beat) * vec3(iParam0, iParam1, iParam2);

    fragColor = vec4(color, 1.0);
}
