// Convert to luminance
// iChannel0: source frame
// iParam0: tint strength (0..1) mixing original with grayscale
void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;
    vec3 tex = texture(iChannel0, uv).rgb;
    float gray = dot(tex, vec3(0.299, 0.587, 0.114));
    vec3 mixed = mix(tex, vec3(gray), clamp(iParam0, 0.0, 1.0));
    fragColor = vec4(mixed, 1.0);
}
