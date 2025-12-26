// 3x3 single-pass blur
// iChannel0: source frame
// iParam1: spread (0..1 -> 0..5 texels)
void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;
    vec2 texel = 1.0 / iResolution.xy;
    float spread = mix(0.0, 5.0, clamp(iParam1, 0.0, 1.0) * clamp(iParam7, 0.0, 1.0));
    vec2 o = texel * spread;
    vec4 sum = texture(iChannel0, uv);
    sum += texture(iChannel0, uv + vec2(-o.x, -o.y));
    sum += texture(iChannel0, uv + vec2(0.0, -o.y));
    sum += texture(iChannel0, uv + vec2(o.x, -o.y));
    sum += texture(iChannel0, uv + vec2(-o.x, 0.0));
    sum += texture(iChannel0, uv + vec2(o.x, 0.0));
    sum += texture(iChannel0, uv + vec2(-o.x, o.y));
    sum += texture(iChannel0, uv + vec2(0.0, o.y));
    sum += texture(iChannel0, uv + vec2(o.x, o.y));
    fragColor = sum / 9.0;
}
