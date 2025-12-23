// Shadertoy-style effect: define mainImage, renderer wrapper injects main().
// Driven entirely by iBeatPulse: higher pulse = stronger glow of previous frame.

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;

    // Previous node's output
    vec3 base = texture(iChannel0, uv).rgb;

    // Beat-driven flash (0..1)
    float flash = clamp(iBeatPulse, 0.0, 1.0);

    // Expose heavily based on beat, then tone-map
    float exposure = mix(1.0, 12.0, flash);          // up to ~12x
    vec3 boosted = base * exposure;

    // Soft clip (Reinhard)
    boosted = boosted / (boosted + vec3(1.0));

    fragColor = vec4(boosted, 1.0);
}