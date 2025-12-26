// Sample a single vertical stripe and stretch across screen
// iChannel0: source frame
// iParam0: stripe X position (0..1), default 0.5
void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;
    float intensity = clamp(iParam7, 0.0, 1.0);
    if (intensity < 0.001) {
        fragColor = texture(iChannel0, uv);
        return;
    }
    float xStripe = clamp(iParam0, 0.0, 1.0);
    vec2 tc = vec2(xStripe, uv.y);
    vec3 striped = texture(iChannel0, tc).rgb;
    vec3 original = texture(iChannel0, uv).rgb;
    fragColor = vec4(mix(original, striped, intensity), 1.0);
}
