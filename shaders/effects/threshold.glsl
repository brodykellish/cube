// Threshold to black/white
// iChannel0: source frame
// iParam0: threshold (0..1), default 0.5
void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;
    vec3 tex = texture(iChannel0, uv).rgb;
    float gray = dot(tex, vec3(0.299, 0.587, 0.114));
    float t = step(clamp(iParam0, 0.0, 1.0), gray);
    fragColor = vec4(vec3(t), 1.0);
}
