// CRT Monitor Effect - Renders input on a retro CRT-style monitor
// iChannel0: source frame
// iParam0: Screen inset (0..1) - how much the screen is inset from the frame
// iParam1: Frame thickness (0..1) - thickness of the monitor bezel
// iParam2: Screen curvature (0..1) - amount of screen curvature effect
// iParam3: Scanline intensity (0..1) - intensity of CRT scanlines

// Simple hash for noise
float hash(vec2 p) {
    return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453);
}

// Smooth step function for rounded corners
float roundedBox(vec2 uv, vec2 size, float radius) {
    vec2 d = abs(uv) - size + radius;
    return min(max(d.x, d.y), 0.0) + length(max(d, 0.0)) - radius;
}

// Screen curvature effect (barrel distortion)
vec2 barrelDistortion(vec2 uv, float amount) {
    vec2 center = vec2(0.5, 0.5);
    vec2 coord = uv - center;
    float dist = length(coord);
    float distortion = 1.0 + amount * dist * dist;
    return center + coord * distortion;
}

// CRT scanlines
float scanlines(vec2 uv, float intensity) {
    float scanlineFreq = 400.0;
    float scanline = sin(uv.y * scanlineFreq * 3.14159) * 0.5 + 0.5;
    scanline = pow(scanline, 16.0);
    return 1.0 - scanline * intensity * 0.15;
}

// Subtle screen glow/vignette
float screenGlow(vec2 uv) {
    vec2 center = vec2(0.5, 0.5);
    float dist = length(uv - center);
    return 1.0 - smoothstep(0.3, 0.7, dist) * 0.1;
}

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;
    vec2 aspect = vec2(iResolution.x / iResolution.y, 1.0);
    
    float intensity = clamp(iParam7, 0.0, 1.0);
    if (intensity < 0.001) {
        fragColor = texture(iChannel0, uv);
        return;
    }
    float screenInset = mix(0.05, 0.15, clamp(iParam0, 0.0, 1.0) * intensity);
    float frameThickness = mix(0.08, 0.2, clamp(iParam1, 0.0, 1.0) * intensity);
    float curvature = clamp(iParam2, 0.0, 1.0) * intensity;
    float scanlineIntensity = clamp(iParam3, 0.0, 1.0) * intensity;
    
    // Normalize UV to center
    vec2 centeredUV = (uv - 0.5) * aspect;
    
    // Define frame and screen areas
    float frameOuter = roundedBox(centeredUV, vec2(0.5, 0.5), 0.02);
    float frameInner = roundedBox(centeredUV, vec2(0.5 - frameThickness, 0.5 - frameThickness), 0.015);
    float screenArea = roundedBox(centeredUV, vec2(0.5 - frameThickness - screenInset, 0.5 - frameThickness - screenInset), 0.01);
    
    // Determine what we're rendering
    bool isFrame = frameOuter < 0.0 && frameInner > 0.0;
    bool isScreen = screenArea < 0.0;
    bool isBezel = frameOuter < 0.0 && !isScreen;
    
    vec3 color = vec3(0.0);
    
    if (isScreen) {
        // Calculate screen UV coordinates (scaled and centered)
        float screenSize = 0.5 - frameThickness - screenInset;
        vec2 screenUV = (centeredUV) / screenSize;
        screenUV = screenUV * 0.5 + 0.5;
        
        // Apply barrel distortion for CRT curvature
        if (curvature > 0.0) {
            screenUV = barrelDistortion(screenUV, curvature * 0.1);
        }
        
        // Clamp UV to prevent sampling outside texture bounds
        screenUV = clamp(screenUV, 0.0, 1.0);
        
        // Sample the input texture
        vec3 screenColor = texture(iChannel0, screenUV).rgb;
        
        // Apply scanlines
        float scanline = scanlines(screenUV, scanlineIntensity);
        screenColor *= scanline;
        
        // Apply subtle screen glow
        screenColor *= screenGlow(screenUV);
        
        // Add slight brightness boost to simulate CRT glow
        screenColor = pow(screenColor, vec3(0.95));
        
        // Add subtle noise for CRT authenticity
        float noise = hash(screenUV * iResolution.xy + iTime * 0.1) * 0.01;
        screenColor += vec3(noise);
        
        color = screenColor;
    } else if (isFrame) {
        // Monitor frame - dark gray/black with subtle gradient
        float frameDist = abs(frameInner) / frameThickness;
        vec3 frameColor = vec3(0.15, 0.15, 0.18);
        
        // Add subtle gradient for depth
        float gradient = 1.0 - frameDist * 0.3;
        frameColor *= gradient;
        
        // Add slight highlight on top edge
        float topEdge = smoothstep(0.0, 0.1, abs(centeredUV.y - (0.5 - frameThickness)));
        topEdge *= step(centeredUV.y, 0.5);
        frameColor += vec3(0.05) * topEdge;
        
        color = frameColor;
    } else if (isBezel) {
        // Outer bezel - very dark
        color = vec3(0.05, 0.05, 0.06);
        
        // Add subtle rounded corner highlight
        float cornerDist = length(max(abs(centeredUV) - vec2(0.45, 0.45), 0.0));
        float cornerHighlight = smoothstep(0.05, 0.0, cornerDist) * 0.1;
        color += vec3(cornerHighlight);
    } else {
        // Outside the monitor - pure black
        color = vec3(0.0);
    }
    
    // Add subtle screen reflection on the frame
    if (isFrame) {
        float screenSize = 0.5 - frameThickness - screenInset;
        vec2 screenUV = (centeredUV) / screenSize;
        screenUV = screenUV * 0.5 + 0.5;
        screenUV = clamp(screenUV, 0.0, 1.0);
        
        // Only show reflection on top portion
        if (centeredUV.y > 0.3 && centeredUV.y < 0.5) {
            float reflection = texture(iChannel0, screenUV).r * 0.05;
            color += vec3(reflection);
        }
    }
    
    fragColor = vec4(color, 1.0);
}

