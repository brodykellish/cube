// Frame differencing: highlight changes between current and previous frame
// iChannel0: current frame
// iChannel1: previous frame (optional). If missing, output current.
// iParam0: gain (0..1 -> 0..4x)
void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;
    vec3 cur = texture(iChannel0, uv).rgb;
    vec3 prev = texture(iChannel1, uv).rgb;
    float gain = mix(1.0, 4.0, clamp(iParam0, 0.0, 1.0) * clamp(iParam7, 0.0, 1.0));
    vec3 diff = (cur - prev) * gain;
    fragColor = vec4(diff, 1.0);
}
