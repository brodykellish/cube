// Webcam invert effect (Shadertoy-style)
// iChannel0: source frame
// Params: none
void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;
    vec3 base = texture(iChannel0, uv).rgb;
    fragColor = vec4(1.0 - base, 1.0);
}
