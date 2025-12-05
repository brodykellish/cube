// Five Spheres - Interactive GLSL shader with MIDI controls
// iParam0: Red color component (0.0-1.0)
// iParam1: Green color component (0.0-1.0)  
// iParam2: Blue color component (0.0-1.0)
// iParam3: Animation speed multiplier (0.0-3.0)

// === SDF ===
float sdSphere(vec3 p, float radius) {
    return length(p) - radius;
}

// === Raymarching ===
float sceneSDF(vec3 p) {
    float animSpeed = iParam3 * 2.0;
    
    // Center sphere
    float sphere1 = sdSphere(p, 0.8);
    
    // Four orbiting spheres arranged in a cross pattern
    float orbitRadius = 2.5;
    float sphereRadius = 0.6;
    
    // Sphere 2: orbits on XZ plane
    vec3 pos2 = vec3(orbitRadius * cos(iTime * animSpeed), 0.0, orbitRadius * sin(iTime * animSpeed));
    float sphere2 = sdSphere(p - pos2, sphereRadius);
    
    // Sphere 3: orbits on XZ plane, offset by 90 degrees
    vec3 pos3 = vec3(orbitRadius * cos(iTime * animSpeed + 1.5708), 0.0, orbitRadius * sin(iTime * animSpeed + 1.5708));
    float sphere3 = sdSphere(p - pos3, sphereRadius);
    
    // Sphere 4: orbits on XY plane
    vec3 pos4 = vec3(orbitRadius * cos(iTime * animSpeed * 0.7), orbitRadius * sin(iTime * animSpeed * 0.7), 0.0);
    float sphere4 = sdSphere(p - pos4, sphereRadius);
    
    // Sphere 5: orbits on YZ plane
    vec3 pos5 = vec3(0.0, orbitRadius * cos(iTime * animSpeed * 1.3), orbitRadius * sin(iTime * animSpeed * 1.3));
    float sphere5 = sdSphere(p - pos5, sphereRadius);
    
    // Union all spheres
    float result = sphere1;
    result = min(result, sphere2);
    result = min(result, sphere3);
    result = min(result, sphere4);
    result = min(result, sphere5);
    
    return result;
}

float raymarch(vec3 ro, vec3 rd, float maxDist) {
    float t = 0.0;
    for (int i = 0; i < 96; i++) {
        vec3 p = ro + rd * t;
        float d = sceneSDF(p);
        if (d < 0.001) return t;
        if (t > maxDist) break;
        t += d * 0.8;
    }
    return -1.0;
}

vec3 calcNormal(vec3 p) {
    float eps = 0.001;
    vec2 h = vec2(eps, 0.0);
    return normalize(vec3(
        sceneSDF(p + h.xyy) - sceneSDF(p - h.xyy),
        sceneSDF(p + h.yxy) - sceneSDF(p - h.yxy),
        sceneSDF(p + h.yyx) - sceneSDF(p - h.yyx)
    ));
}

// === Lighting ===
vec3 simpleLighting(vec3 p, vec3 rd, vec3 normal, vec3 color) {
    // Rotating light source
    vec3 lightPos = vec3(6.0 * sin(iTime * 0.3), 4.0, 6.0 * cos(iTime * 0.3));
    vec3 lightDir = normalize(lightPos - p);

    // Diffuse lighting
    float diff = max(dot(normal, lightDir), 0.0);
    
    // Specular lighting
    vec3 reflectDir = reflect(-lightDir, normal);
    float spec = pow(max(dot(-rd, reflectDir), 0.0), 32.0);

    // Combine lighting components
    vec3 ambient = color * 0.25;
    vec3 diffuse = color * diff * 0.7;
    vec3 specular = vec3(1.0) * spec * 0.4;

    return ambient + diffuse + specular;
}

// === UV Mapping ===
vec2 getSphereUV(vec3 p) {
    vec3 n = normalize(p);
    float theta = atan(n.z, n.x);
    float phi = asin(n.y);

    vec2 uv;
    uv.x = (theta + 3.14159265) / (2.0 * 3.14159265);
    uv.y = (phi + 1.5707963) / 3.14159265;

    return uv;
}

float checkerboard(vec2 uv, float scale) {
    vec2 grid = floor(uv * scale);
    return mod(grid.x + grid.y, 2.0);
}

// === Color variation based on position ===
vec3 getColorVariation(vec3 p) {
    // Create color variation based on world position
    float colorShift = sin(p.x * 0.5) * cos(p.y * 0.3) * sin(p.z * 0.7);
    colorShift = colorShift * 0.3 + 0.7; // Normalize to 0.4-1.0 range
    
    vec3 baseColor = vec3(iParam0, iParam1, iParam2);
    return baseColor * colorShift;
}

// === Main Shader ===
void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    // Setup screen coordinates
    vec2 uv = (fragCoord - 0.5 * iResolution.xy) / iResolution.y;

    // Setup camera using provided uniforms
    vec3 ro = iCameraPos;
    vec3 rd = normalize(uv.x * iCameraRight + uv.y * iCameraUp + iCameraForward);

    // Raymarch the scene
    float t = raymarch(ro, rd, 25.0);

    vec3 color = vec3(0.0, 0.0, 0.0); // Black background

    if (t > 0.0) {
        // Hit something - calculate surface properties
        vec3 p = ro + rd * t;
        vec3 normal = calcNormal(p);
        
        // Get UV coordinates for texture mapping
        vec2 surfaceUV = getSphereUV(p);
        
        // Create base color with position-based variation
        vec3 baseColor = getColorVariation(p);
        
        // Add subtle checkerboard pattern
        float checker = checkerboard(surfaceUV, 12.0);
        baseColor = mix(baseColor, baseColor * 0.7, checker * 0.2);
        
        // Apply lighting
        color = simpleLighting(p, rd, normal, baseColor);
        
        // Add rim lighting for extra visual appeal
        float rimIntensity = 1.0 - abs(dot(normal, -rd));
        rimIntensity = pow(rimIntensity, 3.0);
        color += baseColor * rimIntensity * 0.4;
        
        // Remove atmospheric scattering to maintain pure black background
        // float fog = exp(-t * 0.02);
        // color = mix(vec3(0.1, 0.1, 0.2), color, fog);
    }

    // Gamma correction
    color = pow(color, vec3(0.4545));
    
    fragColor = vec4(color, 1.0);
}