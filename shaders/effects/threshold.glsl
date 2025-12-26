// Threshold to black/white
// iChannel0: source frame
// iParam0: threshold (0..1), default 0.5
void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;
    vec3 tex = texture(iChannel0, uv).rgb;
    float gray = dot(tex, vec3(0.299, 0.587, 0.114));
    float intensity = clamp(iParam7, 0.0, 1.0);
    if (intensity < 0.001) {
        fragColor = vec4(tex, 1.0);
        return;
    }
    float t = step(clamp(iParam0, 0.0, 1.0), gray);
    vec3 result = mix(tex, vec3(t), intensity);
    fragColor = vec4(result, 1.0);
}
