/*
    Image Flash Effect
    -------------------
    Flashes an image onto the screen while the effect is active.
    Additively blends the flash image over the background, treating black as transparent.
    
    Inputs:
    - iChannel0: Current input (background)
    - iChannel1: Flash image to overlay
*/

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;
    
    // Sample background
    vec3 background = texture(iChannel0, uv).rgb;
    
    // Sample flash image
    vec3 flashImage = texture(iChannel1, uv).rgb;
    
    // Calculate brightness of flash image to determine transparency
    // Black pixels (brightness near 0) should be transparent
    float flashBrightness = dot(flashImage, vec3(0.299, 0.587, 0.114));
    
    // Create alpha mask: black pixels are transparent, colored pixels are opaque
    float flashAlpha = smoothstep(0.0, 0.1, flashBrightness);
    
    
    // Additively blend: background + flashImage * intensity * alpha
    vec3 result = background + flashImage * flashAlpha;
    
    fragColor = vec4(result, 1.0);
}

