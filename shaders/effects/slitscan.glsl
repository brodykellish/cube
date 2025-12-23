// Slitscan-style smear by sampling different columns over time
// iChannel0: source frame
// iParam0: scroll speed (0..1 -> 0..1 cycles per second)
// iParam1: shear amount across Y (0..1 -> 0..1)
void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;
    float speed = mix(0.0, 1.0, clamp(iParam0, 0.0, 1.0));
    float shear = mix(0.0, 1.0, clamp(iParam1, 0.0, 1.0));
    float offset = iTime * speed + uv.y * shear;
    uv.x = fract(uv.x - offset);
    fragColor = texture(iChannel0, uv);
}
