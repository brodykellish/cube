// Sample a single vertical stripe and stretch across screen
// iChannel0: source frame
// iParam0: stripe X position (0..1), default 0.5
void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;
    float xStripe = clamp(iParam0, 0.0, 1.0);
    vec2 tc = vec2(xStripe, uv.y);
    fragColor = texture(iChannel0, tc);
}
