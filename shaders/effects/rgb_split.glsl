// RGB channel split with adjustable offset
// iChannel0: source frame
// iParam0: offset amount (0..1) mapped to pixel shift (0..24px)
void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;
    vec2 texel = 1.0 / iResolution.xy;
    float px = mix(0.0, 24.0, clamp(iParam0, 0.0, 1.0));
    vec2 offset = texel * px;
    vec4 rTex = texture(iChannel0, uv - offset);
    vec4 gTex = texture(iChannel0, uv);
    vec4 bTex = texture(iChannel0, uv + offset);
    fragColor = vec4(rTex.r, gTex.g, bTex.b, 1.0);
}
