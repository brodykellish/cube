// Psychedelic Distorted Sphere - Pulsing sphere with noise and distortion effects on a plane with shadows
// iParam0 = Distortion intensity (0.0 = smooth sphere, 1.0 = heavy distortion)
// iParam1 = Noise intensity (0.0 = no noise, 1.0 = heavy noise)
// iParam2 = Sphere size multiplier (0.1 to 2.0)
// iParam3 = Pulse speed multiplier (0.0 = no pulse, 1.0 = fast pulse)

// === Noise Functions ===
float hash(float n) {
    return fract(sin(n) * 43758.5453);
}

float noise(vec3 p) {
    vec3 i = floor(p);
    vec3 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    
    float n = i.x + i.y * 57.0 + 113.0 * i.z;
    return mix(mix(mix(hash(n + 0.0), hash(n + 1.0), f.x),
                   mix(hash(n + 57.0), hash(n + 58.0), f.x), f.y),
               mix(mix(hash(n + 113.0), hash(n + 114.0), f.x),
                   mix(hash(n + 170.0), hash(n + 171.0), f.x), f.y), f.z);
}

float fbm(vec3 p) {
    float value = 0.0;
    float amplitude = 0.5;
    float frequency = 1.0;
    
    for (int i = 0; i < 6; i++) {
        value += amplitude * noise(p * frequency);
        amplitude *= 0.5;
        frequency *= 2.0;
    }
    return value;
}

// === SDF Functions ===
float sdSphere(vec3 p, float radius) {
    return length(p) - radius;
}

float sdPlane(vec3 p, vec3 normal, float offset) {
    return dot(p, normal) + offset;
}

float distortSphere(vec3 p, float baseRadius, float distortAmount, float noiseAmount) {
    // Base sphere distance
    float dist = length(p);
    
    // Add pulsing based on time and iParam3
    float pulseSpeed = iParam3 * 3.0 + 0.5;
    float pulse = sin(iTime * pulseSpeed) * 0.1 + sin(iTime * pulseSpeed * 2.3) * 0.05;
    
    // Create distortion using multiple noise layers
    vec3 noisePos = p * 2.0 + iTime * 0.3;
    float distortion = fbm(noisePos) * distortAmount * 0.3;
    distortion += fbm(noisePos * 2.0 + iTime * 0.5) * distortAmount * 0.2;
    distortion += fbm(noisePos * 4.0 - iTime * 0.7) * distortAmount * 0.1;
    
    // Add random noise effect
    float randomNoise = (noise(p * 8.0 + iTime * 2.0) - 0.5) * noiseAmount * 0.2;
    randomNoise += (noise(p * 16.0 - iTime * 3.0) - 0.5) * noiseAmount * 0.1;
    
    // Combine all effects
    float finalRadius = baseRadius + pulse + distortion + randomNoise;
    
    return dist - finalRadius;
}

// === Scene SDF ===
float sceneSDF(vec3 p) {
    float baseRadius = 1.5 + iParam2 * 1.0; // Fixed size: 1.5 to 2.5 for better visibility
    float distortAmount = iParam0; // Distortion intensity
    float noiseAmount = iParam1; // Noise intensity
    
    // Sphere positioned above ground at origin
    vec3 spherePos = p - vec3(0.0, 0.5, 0.0); // Raise sphere above ground
    float sphere = distortSphere(spherePos, baseRadius, distortAmount, noiseAmount);
    
    // Ground plane at y = -2.0
    float plane = sdPlane(p, vec3(0.0, 1.0, 0.0), 2.0);
    
    return min(sphere, plane);
}

// === Material ID ===
int getMaterialID(vec3 p) {
    float baseRadius = 1.5 + iParam2 * 1.0;
    float distortAmount = iParam0;
    float noiseAmount = iParam1;
    
    vec3 spherePos = p - vec3(0.0, 0.5, 0.0);
    float sphere = distortSphere(spherePos, baseRadius, distortAmount, noiseAmount);
    float plane = sdPlane(p, vec3(0.0, 1.0, 0.0), 2.0);
    
    return (sphere < plane) ? 1 : 0; // 1 = sphere, 0 = plane
}

// === Raymarching ===
float raymarch(vec3 ro, vec3 rd, float maxDist) {
    float t = 0.01; // Start slightly away from camera
    for (int i = 0; i < 100; i++) {
        vec3 p = ro + rd * t;
        float d = sceneSDF(p);
        if (d < 0.001) return t;
        if (t > maxDist) break;
        t += d * 0.8; // Slightly conservative step
    }
    return -1.0;
}

// === Shadow Raymarching ===
float softShadow(vec3 ro, vec3 rd, float mint, float maxt, float k) {
    float res = 1.0;
    for (float t = mint; t < maxt;) {
        float h = sceneSDF(ro + rd * t);
        if (h < 0.001) return 0.0;
        res = min(res, k * h / t);
        t += h;
    }
    return res;
}

// === Normal Calculation ===
vec3 calcNormal(vec3 p) {
    float eps = 0.001;
    vec2 h = vec2(eps, 0.0);
    return normalize(vec3(
        sceneSDF(p + h.xyy) - sceneSDF(p - h.xyy),
        sceneSDF(p + h.yxy) - sceneSDF(p - h.yxy),
        sceneSDF(p + h.yyx) - sceneSDF(p - h.yyx)
    ));
}

// === Static Light Sources ===
struct Light {
    vec3 pos;
    vec3 color;
};

Light getLights(int index) {
    Light lights[5];
    
    // Red light - static position
    lights[0].pos = vec3(4.0, 3.0, 4.0);
    lights[0].color = vec3(1.0, 0.2, 0.2);
    
    // Blue light - static position
    lights[1].pos = vec3(-3.0, 2.5, 3.0);
    lights[1].color = vec3(0.2, 0.2, 1.0);
    
    // Green light - static position
    lights[2].pos = vec3(2.0, 4.0, 2.0);
    lights[2].color = vec3(0.2, 1.0, 0.2);
    
    // Purple light - static position
    lights[3].pos = vec3(-3.0, 4.0, -2.0);
    lights[3].color = vec3(1.0, 0.2, 1.0);
    
    // Orange light - static position
    lights[4].pos = vec3(2.0, 2.0, -2.0);
    lights[4].color = vec3(1.0, 0.6, 0.1);
    
    return lights[index];
}

// === Metallic Sphere Color (Enhanced for visibility) ===
vec3 sphereColor(vec3 p, vec3 normal, float t) {
    // Brighter metallic base color for better visibility
    vec3 baseColor = vec3(0.8, 0.8, 0.9);
    
    // Add surface variation
    float surfaceNoise = fbm(p * 5.0) * 0.2;
    baseColor += vec3(surfaceNoise * 0.3);
    
    // Add psychedelic color variation based on position and time
    vec3 psychColor = vec3(
        0.5 + 0.5 * sin(p.x * 2.0 + iTime),
        0.5 + 0.5 * sin(p.y * 2.0 + iTime * 1.3),
        0.5 + 0.5 * sin(p.z * 2.0 + iTime * 0.7)
    ) * 0.3;
    
    baseColor = mix(baseColor, psychColor, iParam0 * 0.5 + iParam1 * 0.3);
    
    // Keep it bright enough to see
    baseColor = clamp(baseColor, vec3(0.5), vec3(1.2));
    
    return baseColor;
}

// === Plane Pattern ===
vec3 planeColor(vec3 p) {
    vec2 uv = p.xz;
    
    // Checkerboard pattern
    float checker = mod(floor(uv.x * 2.0) + floor(uv.y * 2.0), 2.0);
    vec3 col1 = vec3(0.3);
    vec3 col2 = vec3(0.7);
    
    // Static subtle coloring
    vec3 psychCol = vec3(
        0.1 + 0.1 * sin(uv.x * 0.5),
        0.1 + 0.1 * sin(uv.y * 0.5),
        0.1 + 0.1 * sin(length(uv) * 0.3)
    );
    
    return mix(col1, col2, checker) + psychCol * 0.3;
}

// === Enhanced Lighting for Better Visibility ===
vec3 lighting(vec3 p, vec3 rd, vec3 normal, vec3 baseColor, int materialID) {
    vec3 finalColor = vec3(0.0);
    vec3 ambient = baseColor * 0.3; // Increased ambient for visibility
    
    // Calculate lighting from all light sources
    for (int i = 0; i < 5; i++) {
        Light light = getLights(i);
        vec3 lightDir = normalize(light.pos - p);
        float lightDist = length(light.pos - p);
        
        // Calculate shadow
        float shadow = softShadow(p + normal * 0.01, lightDir, 0.02, lightDist, 8.0);
        shadow = max(shadow, 0.3); // Prevent complete darkness
        
        // Attenuation
        float attenuation = 1.0 / (1.0 + 0.05 * lightDist + 0.005 * lightDist * lightDist);
        
        // Diffuse lighting
        float diff = max(dot(normal, lightDir), 0.0);
        
        // Enhanced specular lighting
        vec3 reflectDir = reflect(-lightDir, normal);
        float spec;
        if (materialID == 1) {
            spec = pow(max(dot(-rd, reflectDir), 0.0), 32.0);
        } else {
            spec = pow(max(dot(-rd, reflectDir), 0.0), 16.0);
        }
        
        // Combine this light's contribution
        vec3 diffuse = baseColor * diff * light.color * attenuation * shadow * 1.5;
        vec3 specular = light.color * spec * attenuation * shadow * 0.8;
        
        finalColor += diffuse + specular;
    }
    
    // Enhanced rim lighting for sphere
    if (materialID == 1) {
        float rimLight = 1.0 - abs(dot(normal, -rd));
        rimLight = pow(rimLight, 1.5);
        vec3 rimColor = vec3(1.0, 0.8, 0.9);
        vec3 rim = rimColor * rimLight * 0.6;
        finalColor += rim;
    }
    
    return ambient + finalColor;
}

// === Main Shader ===
void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = (fragCoord - 0.5 * iResolution.xy) / iResolution.y;
    
    // Camera setup using provided uniforms
    vec3 ro = iCameraPos;
    vec3 rd = normalize(uv.x * iCameraRight + uv.y * iCameraUp + iCameraForward);
    
    // Raymarch the scene
    float t = raymarch(ro, rd, 50.0);
    
    vec3 col = vec3(0.1); // Slightly brighter background for contrast
    
    if (t > 0.0) {
        // Hit something
        vec3 p = ro + rd * t;
        vec3 normal = calcNormal(p);
        int materialID = getMaterialID(p);
        
        vec3 baseColor;
        if (materialID == 1) {
            // Sphere - enhanced metallic with psychedelic elements
            baseColor = sphereColor(p, normal, t);
        } else {
            // Plane - checkered pattern
            baseColor = planeColor(p);
        }
        
        // Apply enhanced lighting
        col = lighting(p, rd, normal, baseColor, materialID);
        
        // Add atmospheric glow for sphere
        if (materialID == 1) {
            float glow = exp(-t * 0.02);
            col += baseColor * glow * 0.2;
        }
    } else {
        // Enhanced background with subtle color
        float backgroundIntensity = 0.1 + iParam0 * 0.05 + iParam1 * 0.025;
        col = vec3(
            0.1 + 0.05 * sin(uv.x * 2.0),
            0.1 + 0.05 * cos(uv.y * 2.0),
            0.15 + 0.05 * sin(length(uv) * 3.0)
        ) * backgroundIntensity;
    }
    
    // Final color adjustment
    col = pow(col, vec3(0.9)); // Less aggressive gamma
    col = clamp(col, vec3(0.0), vec3(2.0)); // Allow brighter colors
    
    fragColor = vec4(col, 1.0);
}