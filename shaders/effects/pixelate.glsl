// Pixelate the image by snapping UVs to a tile grid
// iChannel0: source frame
// iParam0: tile count vertically (0..1 -> 5..120)
void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;
    float tiles = mix(5.0, 120.0, clamp(iParam0, 0.0, 1.0));
    vec2 grid = floor(uv * tiles) / tiles;
    fragColor = texture(iChannel0, grid);
}
