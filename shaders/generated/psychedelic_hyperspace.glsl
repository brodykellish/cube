// Hyperspace Star Field - Stars shooting past camera in streaky trails
// iParam0 = speed (0.0 = slow, 1.0 = hyperspace fast)
// iParam1 = star density (0.0 = few stars, 1.0 = many stars)
// iParam2 = trail length (0.0 = short trails, 1.0 = long streaks)
// iParam3 = brightness (0.0 = dim, 1.0 = bright)

// Improved hash functions for better randomness and less periodicity
float hash(float n) {
    return fract(sin(n * 1234.567) * 43758.5453123);
}

float hash2(float n) {
    return fract(sin(n * 2345.678) * 23421.63271);
}

vec2 hash2_vec(float n) {
    return vec2(
        hash(n * 1.23),
        hash(n * 4.56 + 78.9)
    );
}

vec3 hash3(float n) {
    return vec3(
        fract(sin(n * 1234.567) * 43758.5453123),
        fract(cos(n * 2345.678) * 23421.63271),
        fract(sin(n * 3456.789 + 12.34) * 65432.17891)
    ) * 2.0 - 1.0;
}

// Additional hash for better distribution
float hash3_extra(float n) {
    return fract(tan(n * 987.654 + 321.0) * 87654.32109);
}

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = (fragCoord - 0.5 * iResolution.xy) / iResolution.y;
    
    // Create ray direction from camera
    vec3 rayDir = normalize(uv.x * iCameraRight + uv.y * iCameraUp + 1.5 * iCameraForward);
    
    vec3 color = vec3(0.0);
    
    // Star parameters
    float speed = 1.0 + iParam0 * 25.0; // Speed multiplier
    float density = 0.5 + iParam1 * 3.0; // Star density
    float trailLength = 0.5 + iParam2 * 4.0; // Trail length multiplier
    float brightness = 0.3 + iParam3 * 1.5; // Brightness multiplier
    
    // Generate stars randomly in cone formation around forward direction
    for (int i = 0; i < 200; i++) {
        float starId = float(i) + 1.0;
        
        // Use multiple hash layers for better randomness
        vec3 randVals = hash3(starId * 123.456789);
        float extraRand1 = hash3_extra(starId * 456.789123);
        float extraRand2 = hash2(starId * 789.123456);
        
        // Generate random direction within a cone around the camera's forward direction
        // Cone half-angle (in radians) - controls how wide the cone is
        float coneHalfAngle = 1.2; // About 68 degrees - adjust this for wider/narrower cone
        
        // Generate uniform random point on unit circle for cone base
        float phi = hash(starId * 147.258) * 6.28318530718; // Random angle 0 to 2π
        float cosTheta = 1.0 - hash2(starId * 369.147) * (1.0 - cos(coneHalfAngle)); // Uniform distribution in cone
        float sinTheta = sqrt(max(0.0, 1.0 - cosTheta * cosTheta));
        
        // Create local coordinate system aligned with camera forward
        vec3 forward = normalize(iCameraForward);
        vec3 right = normalize(iCameraRight);
        vec3 up = normalize(iCameraUp);
        
        // Generate direction within cone using spherical coordinates
        vec3 coneDir = vec3(
            sinTheta * cos(phi),
            sinTheta * sin(phi),
            cosTheta
        );
        
        // Transform cone direction from local space to world space
        vec3 starDir = normalize(
            coneDir.x * right +
            coneDir.y * up +
            coneDir.z * forward
        );
        
        // Add some variation to prevent perfect cone alignment
        vec3 randomOffset = hash3(starId * 0.987654) * 0.2;
        starDir = normalize(starDir + randomOffset);
        
        // More varied spawn time offset using multiple hash sources
        float timeOffset = mix(
            hash(starId * 0.789123) * 50.0,
            hash3_extra(starId * 1.234567) * 30.0,
            extraRand1
        );
        
        // Add some low-frequency variation to prevent regularity
        timeOffset += sin(starId * 0.1234) * 5.0 + cos(starId * 0.5678) * 3.0;
        
        // Stars start at origin and travel outward along starDir
        float starTime = iTime * speed + timeOffset;
        
        // Use non-periodic distance calculation with varied cycle lengths
        float cycleLength = 40.0 + extraRand2 * 30.0; // Varied cycle lengths from 40 to 70
        float distance = mod(starTime + sin(starId * 0.314159) * 10.0, cycleLength);
        
        // Star position - moves outward from origin along starDir
        vec3 starPos = starDir * distance;
        
        // Transform star position relative to camera
        vec3 relativePos = starPos - iCameraPos;
        
        // Check if star is in front of camera
        float forwardDot = dot(relativePos, iCameraForward);
        if (forwardDot > 0.1 && length(relativePos) > 0.5) {
            // Star must be at least 2 units from origin to be visible (fade in zone)
            float originDistance = length(starPos);
            if (originDistance > 2.0) {
                // Project star onto screen plane
                float depth = forwardDot;
                vec2 screenPos = vec2(
                    dot(relativePos, iCameraRight) / depth,
                    dot(relativePos, iCameraUp) / depth
                ) / 1.5;
                
                // Skip stars too far from screen to optimize
                if (length(screenPos) < 3.0) {
                    // Create multiple trail segments with varied spacing
                    float trailStep = 0.08 + extraRand1 * 0.04; // Vary trail segment spacing
                    for (float t = 0.0; t <= trailLength; t += trailStep) {
                        // Calculate previous position of star (closer to origin)
                        float pastTime = starTime - t * speed * 0.1;
                        float pastDistance = mod(pastTime + sin(starId * 0.314159) * 10.0, cycleLength);
                        vec3 pastStarPos = starDir * pastDistance;
                        
                        // Only show trail if past position is also far enough from origin
                        if (length(pastStarPos) > 2.0) {
                            vec3 pastRelativePos = pastStarPos - iCameraPos;
                            
                            float pastForwardDot = dot(pastRelativePos, iCameraForward);
                            if (pastForwardDot > 0.1) {
                                // Project past position onto screen
                                float pastDepth = pastForwardDot;
                                vec2 pastScreenPos = vec2(
                                    dot(pastRelativePos, iCameraRight) / pastDepth,
                                    dot(pastRelativePos, iCameraUp) / pastDepth
                                ) / 1.5;
                                
                                // Distance from current pixel to this trail segment
                                float pixelDist = length(uv - pastScreenPos);
                                
                                // Trail intensity - fades with time and distance
                                float trailFade = exp(-t / trailLength * 3.0); // Exponential fade along trail
                                float distanceFade = exp(-length(pastRelativePos) * 0.1); // Fade with distance
                                float sizeFade = 1.0 / (1.0 + pixelDist * pixelDist * 5000.0); // Sharp falloff
                                
                                // Fade in near origin (smooth transition from invisible to visible)
                                float pastOriginDistance = length(pastStarPos);
                                float originFade = smoothstep(2.0, 4.0, pastOriginDistance);
                                
                                float trailIntensity = trailFade * distanceFade * sizeFade * brightness * 0.3 * originFade;
                                
                                // Trail color - slightly blue-shifted
                                vec3 trailColor = vec3(0.7, 0.8, 1.0);
                                
                                // Random color variation for some stars using better distribution
                                float colorVar = hash(starId * 0.456789);
                                if (colorVar > 0.8) trailColor = vec3(1.0, 0.7, 0.6); // Orange
                                else if (colorVar > 0.6) trailColor = vec3(0.7, 1.0, 0.7); // Green
                                
                                color += trailColor * trailIntensity;
                            }
                        }
                    }
                    
                    // Main star core - brighter than trail
                    float pixelDist = length(uv - screenPos);
                    float starIntensity = 1.0 / (1.0 + pixelDist * pixelDist * 10000.0);
                    starIntensity *= brightness;
                    starIntensity *= exp(-length(relativePos) * 0.05); // Distance fade
                    
                    // Fade in near origin (smooth transition from invisible to visible)
                    float originFade = smoothstep(2.0, 4.0, originDistance);
                    starIntensity *= originFade;
                    
                    // Star core color - pure white/blue
                    vec3 starColor = vec3(1.0, 1.0, 1.2);
                    
                    // Random color variation using improved hash
                    float colorVar = hash(starId * 0.456789);
                    if (colorVar > 0.8) starColor = vec3(1.2, 0.9, 0.7); // Orange
                    else if (colorVar > 0.6) starColor = vec3(0.8, 1.2, 0.8); // Green
                    
                    color += starColor * starIntensity;
                }
            }
        }
    }
    
    // Apply density control
    color *= density * 0.5;
    
    fragColor = vec4(color, 1.0);
}