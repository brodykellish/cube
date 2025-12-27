// Tiled sprite animation
// Loads office_sprites.ichannel0 and tiles it continuously, translating down and to the right
// iChannel0: sprite sheet image
// iParam0: zoom factor (controls number of tiles visible, 0-1 maps to 2.0-8.0 tiles)
// iParam5: translation speed (0-1 maps to 0-0.2 UV units per second)

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;
    
    // Tile scale from iParam0 (zoom factor)
    // Maps 0-1 to 2.0-8.0, where smaller values = fewer tiles, larger values = more tiles
    float tileScale = mix(0.5, 2.0, clamp(iParam0, 0.0, 1.0));
    
    // Speed of translation from iParam5
    // Maps 0-1 to 0-0.2 UV units per second
    float speed = mix(0.0, 0.2, clamp(iParam5, 0.0, 1.0));
    
    // Calculate translation offset based on time
    // Moving down and to the right (subtract offset so texture scrolls in that direction)
    vec2 offset = vec2(iTime * speed, iTime * speed);
    
    // Create tiled UV coordinates with translation
    // Using fract() to create repeating pattern
    // Subtracting offset makes the texture scroll down and to the right
    vec2 tiledUV = fract(uv * tileScale - offset);
    
    // Sample the texture at the tiled and translated coordinates
    vec3 color = texture(iChannel0, tiledUV).rgb;
    
    fragColor = vec4(color, 1.0);
}

