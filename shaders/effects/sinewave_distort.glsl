// Vertical sine-wave distortion of UVs
// iChannel0: source frame
// iParam0: frequency (0..1 -> 0..24 waves)
// iParam1: amplitude (0..1 -> 0..0.1 UV units)
void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;
    float freq = mix(0.0, 24.0, clamp(iParam0, 0.0, 1.0));
    float amp = mix(0.0, 0.1, clamp(iParam1, 0.0, 1.0));
    float wave = sin(uv.y * freq + iTime) * amp;
    vec2 distorted = uv + vec2(wave, 0.0);
    fragColor = texture(iChannel0, distorted);
}
