// Beat Pulse - BPM-synchronized visualization
// Demonstrates the beat trigger system
// Pulsates and changes color in sync with detected beats

void mainImage(out vec4 fragColor, vec2 fragCoord) {
    vec2 uv = (fragCoord - 0.5 * iResolution.xy) / iResolution.y;
    float dist = length(uv);

    // Use beat trigger (0-1 with ADSR envelope on each beat)
    float trigger = iBeatTrigger;

    // If no tempo detected, show dark
    if (trigger == 0.0 && iBPM == 0.0) {
        fragColor = vec4(0.05, 0.05, 0.1, 1.0);
        return;
    }

    // Calculate beat phase from time and BPM (0-1 over beat cycle)
    float beatDuration = (iBPM > 0.0) ? (60.0 / iBPM) : 1.0;
    float beatPhase = mod(iTime, beatDuration) / beatDuration;

    // Smooth pulsing based on trigger
    float pulse = trigger;

    // Create concentric rings that expand from center on each beat
    float rings = fract(dist * 8.0 - beatPhase * 2.0);
    rings = smoothstep(0.0, 0.1, rings) * smoothstep(0.3, 0.2, rings);

    // Circle size modulated by beat trigger
    float circleSize = 0.3 + pulse * 0.2;
    float circle = smoothstep(circleSize + 0.05, circleSize, dist);

    // Color changes with beat phase (cycles through spectrum)
    vec3 color1 = vec3(1.0, 0.3, 0.5);  // Pink
    vec3 color2 = vec3(0.3, 0.8, 1.0);  // Cyan
    vec3 color3 = vec3(1.0, 0.8, 0.2);  // Yellow

    vec3 color;
    if (beatPhase < 0.5) {
        color = mix(color1, color2, beatPhase * 2.0);
    } else {
        color = mix(color2, color3, (beatPhase - 0.5) * 2.0);
    }

    // Combine elements
    vec3 col = vec3(0.0);
    col += circle * color * (0.5 + pulse * 0.5);  // Main circle
    col += rings * color * 0.3;  // Expanding rings
    col += trigger * vec3(1.0);  // White flash on beat

    // Background gradient
    col += vec3(0.05, 0.05, 0.1) * (1.0 - dist * 0.5);

    fragColor = vec4(col, 1.0);
}
