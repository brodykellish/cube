// Beat Pulse - BPM-synchronized visualization
// Demonstrates the BPM detection system
// Pulsates and changes color in sync with detected beats

void mainImage(out vec4 fragColor, vec2 fragCoord) {
    vec2 uv = (fragCoord - 0.5 * iResolution.xy) / iResolution.y;
    float dist = length(uv);

    // Use beat phase for smooth pulsing (0-1 over the beat cycle)
    float pulse = sin(iBeatPhase * 6.28318) * 0.5 + 0.5;  // 0-1 sine wave

    // Use beat pulse for sharp attacks (1.0 on beat, decays to 0)
    float flash = iBeatPulse;

    // Create concentric rings that expand from center on each beat
    float rings = fract(dist * 8.0 - iBeatPhase * 2.0);
    rings = smoothstep(0.0, 0.1, rings) * smoothstep(0.3, 0.2, rings);

    // Circle size modulated by beat phase
    float circleSize = 0.3 + pulse * 0.2;
    float circle = smoothstep(circleSize + 0.05, circleSize, dist);

    // Color changes with beat phase (cycles through spectrum)
    vec3 color1 = vec3(1.0, 0.3, 0.5);  // Pink
    vec3 color2 = vec3(0.3, 0.8, 1.0);  // Cyan
    vec3 color3 = vec3(1.0, 0.8, 0.2);  // Yellow

    vec3 color;
    if (iBeatPhase < 0.5) {
        color = mix(color1, color2, iBeatPhase * 2.0);
    } else {
        color = mix(color2, color3, (iBeatPhase - 0.5) * 2.0);
    }

    // Combine elements
    vec3 col = vec3(0.0);
    col += circle * color * (0.5 + pulse * 0.5);  // Main circle
    col += rings * color * 0.3;  // Expanding rings
    col += flash * vec3(1.0);  // White flash on beat

    // Add BPM display (small indicator in corner)
    vec2 cornerPos = fragCoord - vec2(30.0, iResolution.y - 30.0);
    float indicator = 1.0 - smoothstep(5.0, 10.0, length(cornerPos));
    col += indicator * color * (0.3 + flash * 0.7);

    // Background gradient
    col += vec3(0.05, 0.05, 0.1) * (1.0 - dist * 0.5);

    fragColor = vec4(col, 1.0);
}
