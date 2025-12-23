// Mirror the frame across both axes
// iChannel0: source frame
// iParam0: horizontal mirror strength (0 none, 1 full) default 1
// iParam1: vertical mirror strength (0 none, 1 full) default 1
void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;
    float mx = clamp(iParam0, 0.0, 1.0);
    float my = clamp(iParam1, 0.0, 1.0);
    uv = mix(uv, abs(uv * 2.0 - 1.0), vec2(mx, my));
    fragColor = texture(iChannel0, uv);
}
