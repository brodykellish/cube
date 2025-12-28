// Tiled sprite animation
// Loads office_sprites.ichannel0 and tiles it continuously, translating down and to the right
// iChannel0: sprite sheet image
// iParam4: zoom factor (controls number of tiles visible, 0-1 maps to 2.0-8.0 tiles)
// iParam5: translation speed (0-1 maps to 0-0.2 UV units per second)

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    // Expand the UV space to cover a larger area than just [0,1]
    // This ensures sprites are tiled beyond visible bounds, preventing borders when effects distort
    vec2 uv = fragCoord / iResolution.xy;
    vec2 expandedUV = uv * 2.0 - 0.5; // Expand to [-0.5, 1.5] range, covering 2x the visible area
    
    float intensity = clamp(iParam7, 0.0, 1.0);
    
    // Tile scale from iParam4 (zoom factor)
    // Maps 0-1 to 2.0-8.0, where smaller values = fewer tiles, larger values = more tiles
    float tileScale = mix(0.5, 2.0, clamp(iParam4, 0.0, 1.0) * intensity);
    
    // Speed of translation from iParam5
    // Maps 0-1 to 0-0.2 UV units per second
    float speed = mix(0.0, 0.2, clamp(iParam5, 0.0, 1.0) * intensity);
    
    // Calculate translation offset based on time
    // Moving down and to the right (subtract offset so texture scrolls in that direction)
    vec2 offset = vec2(iTime * speed, iTime * speed);
    
    // Create tiled UV coordinates with translation
    // Using fract() to create repeating pattern - this ensures seamless tiling
    // Subtracting offset makes the texture scroll down and to the right
    vec2 tiledUV = fract(expandedUV * tileScale - offset);
    
    // Sample the texture at the tiled and translated coordinates
    vec3 color = texture(iChannel0, tiledUV).rgb;
    
    fragColor = vec4(color, 1.0);
}

