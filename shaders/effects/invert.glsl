// Webcam invert effect (Shadertoy-style)
// iChannel0: source frame
// Params: none
void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;
    vec3 base = texture(iChannel0, uv).rgb;
    float intensity = clamp(iParam7, 0.0, 1.0);
    vec3 inverted = 1.0 - base;
    fragColor = vec4(mix(base, inverted, intensity), 1.0);
}
