// Pixelate the image by snapping UVs to a tile grid
// iChannel0: source frame
// iParam0: tile count vertically (0..1 -> 5..120)
void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;
    float intensity = clamp(iParam7, 0.0, 1.0);
    if (intensity < 0.001) {
        fragColor = texture(iChannel0, uv);
        return;
    }
    float tiles = mix(5.0, 120.0, clamp(iParam0, 0.0, 1.0) * intensity);
    vec2 grid = floor(uv * tiles) / tiles;
    vec3 pixelated = texture(iChannel0, grid).rgb;
    vec3 original = texture(iChannel0, uv).rgb;
    fragColor = vec4(mix(original, pixelated, intensity), 1.0);
}
