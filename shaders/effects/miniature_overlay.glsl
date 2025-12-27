// Trailing effect with feedback
// iChannel0: input from previous node (source)
// iChannel1: previous frame output (feedback)
// direction: vec2 uniform - normalized direction vector (magnitude 1) for translation
// iParam7: intensity (0..1, controls effect strength)

uniform vec2 direction;

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;
    float intensity = clamp(iParam7, 0.0, 1.0);
    
    if (intensity < 0.001) {
        fragColor = texture(iChannel0, uv);
        return;
    }
    
    // Start with source layer (iChannel0) - base layer
    vec4 source = texture(iChannel0, uv);
    
    // Calculate translation offset from direction vector
    // Direction is normalized (magnitude 1), scale it to pixel space
    // Use a small step size to create smooth trailing
    float stepSize = 0.04; // Translation step in UV space (increased by 2x)
    vec2 offset = direction * stepSize;
    
    // Sample previous frame (iChannel1) translated by direction
    vec2 translatedUV = uv - offset;
    vec4 feedback = texture(iChannel1, translatedUV);
    
    // Composite: source layer first, then translated feedback on top
    // This creates a trailing tail effect
    fragColor = max(source, feedback);
    }
