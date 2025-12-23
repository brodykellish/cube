// Mosaic displacement effect
// iChannel0: source frame
// iParam0: number of squares vertically (0..1 -> 5..120)
// iParam1: jitter/displacement amount (0..1 -> 0..0.15 UV)
void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;
    float aspect = iResolution.x / iResolution.y;
    float squares = mix(5.0, 120.0, clamp(iParam0, 0.0, 1.0));
    float amt = mix(0.0, 0.15, clamp(iParam1, 0.0, 1.0));
    float offset = amt * 0.5;
    vec2 tc = uv;
    vec2 centered = uv - 0.5;
    centered.x *= aspect;
    vec2 tile = fract(centered * squares + 0.5) * amt;
    fragColor = texture(iChannel0, tc + tile - offset);
}
