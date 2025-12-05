// Beach waves with realistic wave motion and foam - beach and ocean view
// iParam0: Wave frequency (0.0 = slow, 1.0 = fast)
// iParam1: Wave height/amplitude
// iParam2: Foam intensity
// iParam3: Water color mix (blue to green)
// Camera locked above horizon with minimum elevation

#define PI 3.14159265359
#define TAU 6.28318530718
#define MIN_CAMERA_HEIGHT 0.5  // Minimum camera height above water level

// Noise function
float hash(vec2 p) {
    return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

float noise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    return mix(
        mix(hash(i), hash(i + vec2(1, 0)), f.x),
        mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), f.x),
        f.y
    );
}

float fbm(vec2 p) {
    float value = 0.0;
    float amplitude = 0.5;
    for (int i = 0; i < 4; i++) {
        value += amplitude * noise(p);
        p *= 2.0;
        amplitude *= 0.5;
    }
    return value;
}

// Gerstner wave function for realistic ocean waves
float gerstnerWave(vec2 pos, vec2 direction, float steepness, float wavelength, float speed, float time) {
    float k = TAU / wavelength;
    float c = sqrt(9.8 / k);
    vec2 d = normalize(direction);
    float f = k * (dot(d, pos) - c * speed * time);
    return steepness / k * sin(f);
}

// Beach height function - creates sloping sand
float beachHeight(vec3 p) {
    // Simple beach slope - higher near z=0 (shore), slopes down into water
    float beachSlope = smoothstep(-2.0, 5.0, p.z) * 1.5;
    
    // Add sand dunes and texture
    float dunes = sin(p.x * 0.3) * cos(p.z * 0.2) * 0.3;
    float sandTexture = fbm(p.xz * 2.0) * 0.1;
    
    return beachSlope + dunes + sandTexture - 0.3; // Offset so water level is at y=0
}

// Water height with waves - only in water areas
float waterHeight(vec3 p) {
    float waveFreq = 0.3 + iParam0 * 2.0;
    float waveHeight = 0.3 + iParam1 * 1.2;
    float time = iTime;
    
    vec2 pos = p.xz;
    float height = 0.0;
    
    // Primary wave train
    height += gerstnerWave(pos, vec2(0, 1), waveHeight * 0.8, 4.0 / waveFreq, 1.0, time) * 0.6;
    height += gerstnerWave(pos, vec2(0.3, 1), waveHeight * 0.6, 2.5 / waveFreq, 0.8, time) * 0.4;
    height += gerstnerWave(pos, vec2(-0.2, 1), waveHeight * 0.4, 1.8 / waveFreq, 0.6, time) * 0.3;
    height += gerstnerWave(pos, vec2(1, 0.2), waveHeight * 0.5, 3.2 / waveFreq, 0.9, time) * 0.35;
    height += gerstnerWave(pos, vec2(-0.8, -0.6), waveHeight * 0.4, 2.8 / waveFreq, 0.7, time) * 0.25;
    
    // High frequency surface detail
    height += sin(pos.x * 3.0 * waveFreq - time * 4.0) * waveHeight * 0.1;
    height += sin(pos.y * 4.0 * waveFreq - time * 3.0 + pos.x * 0.5) * waveHeight * 0.08;
    
    // Ocean swell
    height += sin(pos.y * 0.2 - time * 0.5) * waveHeight * 0.4;
    height += sin(pos.x * 0.15 - time * 0.3) * waveHeight * 0.3;
    height += sin((pos.x + pos.y) * 0.1 - time * 0.4) * waveHeight * 0.25;
    
    return height;
}

// Combined terrain SDF - beach and water on 2D plane
vec2 sceneSDF(vec3 p) {
    float beach = beachHeight(p);
    float water = waterHeight(p);
    
    // Determine if we're in water or on beach based on position
    // Water exists where z < 0 (negative z), beach where z >= 0
    if (p.z < 0.0) {
        // In water area - use water height
        return vec2(p.y - water, 1.0); // Material 1 = water
    } else {
        // On beach area - use beach height  
        return vec2(p.y - beach, 2.0); // Material 2 = sand
    }
}

// Calculate normal
vec3 calcNormal(vec3 p) {
    vec2 e = vec2(0.002, 0.0);
    return normalize(vec3(
        sceneSDF(p + e.xyy).x - sceneSDF(p - e.xyy).x,
        sceneSDF(p + e.yxy).x - sceneSDF(p - e.yxy).x,
        sceneSDF(p + e.yyx).x - sceneSDF(p - e.yyx).x
    ));
}

// Raymarching
vec2 raymarch(vec3 ro, vec3 rd) {
    float t = 0.1;
    float material = 0.0;
    
    for (int i = 0; i < 120; i++) {
        vec3 p = ro + rd * t;
        vec2 d = sceneSDF(p);
        
        if (abs(d.x) < 0.002) {
            material = d.y;
            break;
        }
        
        t += max(d.x * 0.7, 0.01);
        
        if (t > 50.0) break;
    }
    
    return vec2(t, material);
}

// Enhanced foam calculation for water areas
float calculateFoam(vec3 p) {
    // Only calculate foam in water areas
    if (p.z >= 0.0) return 0.0;
    
    float waveHeight = waterHeight(p);
    
    // Foam at wave crests
    float foamFromCrest = smoothstep(0.1, 0.4, waveHeight) * 0.6;
    
    // Animated foam texture
    vec2 foamUV = vec2(p.x * 2.0 + iTime * 0.5, p.z * 2.0 - iTime * 1.5);
    float foamNoise = fbm(foamUV) * fbm(foamUV * 2.0) * 0.7;
    
    // Extra foam near shore (where z approaches 0)
    float shoreFoam = smoothstep(-1.0, 0.0, p.z) * 0.8;
    
    return (foamFromCrest + shoreFoam) * foamNoise * iParam2;
}

// Lighting
vec3 lighting(vec3 p, vec3 rd, vec3 normal, float material) {
    vec3 lightDir = normalize(vec3(0.4, 0.8, -0.4));
    vec3 lightColor = vec3(1.0, 0.95, 0.85);
    
    vec3 ambient = vec3(0.4, 0.5, 0.7);
    
    // Diffuse
    float diff = max(0.0, dot(normal, lightDir));
    vec3 diffuse = lightColor * diff;
    
    // Specular
    vec3 reflectDir = reflect(-lightDir, normal);
    float spec = pow(max(0.0, dot(-rd, reflectDir)), 64.0);
    vec3 specular = lightColor * spec;
    
    vec3 color;
    
    if (material == 1.0) { // Water
        // Water color based on iParam3
        vec3 waterBlue = vec3(0.05, 0.25, 0.6);
        vec3 waterGreen = vec3(0.1, 0.4, 0.35);
        vec3 baseColor = mix(waterBlue, waterGreen, iParam3);
        
        // Calculate foam
        float foam = calculateFoam(p);
        vec3 foamColor = vec3(0.95, 0.98, 1.0);
        
        // Mix water and foam
        color = mix(baseColor, foamColor, clamp(foam, 0.0, 1.0));
        
        // Apply lighting with strong specular for water
        color = color * (ambient * 0.8 + diffuse * 0.9) + specular * 1.2;
        
        // Add depth-based transparency
        float depth = length(p - iCameraPos);
        float transparency = exp(-depth * 0.1);
        vec3 deepWaterColor = vec3(0.02, 0.1, 0.3);
        color = mix(deepWaterColor, color, transparency);
        
    } else if (material == 2.0) { // Beach/Sand
        // Sandy beach colors
        vec3 sandLight = vec3(0.9, 0.8, 0.6);
        vec3 sandDark = vec3(0.7, 0.6, 0.4);
        
        // Add sand texture variation
        float sandVariation = fbm(p.xz * 5.0) * 0.3 + 0.7;
        vec3 sandColor = mix(sandDark, sandLight, sandVariation);
        
        // Apply lighting (less specular than water)
        color = sandColor * (ambient * 1.2 + diffuse * 0.8) + specular * 0.1;
        
        // Wet sand near water (darker and more reflective)
        float distanceToWater = max(0.0, p.z);
        float wetness = exp(-distanceToWater * 2.0);
        vec3 wetSandColor = sandColor * 0.4;
        color = mix(color, wetSandColor, wetness * 0.7);
        color += specular * wetness * 0.5; // Wet sand reflects more
        
    } else { // Sky/background
        float skyGrad = 0.5 + 0.5 * rd.y;
        color = mix(vec3(0.85, 0.9, 1.0), vec3(0.3, 0.6, 1.0), skyGrad);
    }
    
    return color;
}

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    // Setup camera using Shadertoy camera uniforms with height clamping
    vec2 uv = (fragCoord - 0.5 * iResolution.xy) / iResolution.y;
    
    // Clamp camera position to maintain minimum height above terrain
    vec3 ro = iCameraPos;
    
    // Get terrain height at camera position for dynamic clamping
    float terrainHeightAtCamera;
    if (ro.z < 0.0) {
        terrainHeightAtCamera = waterHeight(ro);
    } else {
        terrainHeightAtCamera = beachHeight(ro);
    }
    
    float minAllowedHeight = terrainHeightAtCamera + MIN_CAMERA_HEIGHT;
    ro.y = max(ro.y, minAllowedHeight);
    
    vec3 rd = normalize(uv.x * iCameraRight + uv.y * iCameraUp + iCameraForward);
    
    // Raymarch the scene
    vec2 result = raymarch(ro, rd);
    float t = result.x;
    float material = result.y;
    
    vec3 color;
    
    if (t < 50.0 && material > 0.0) {
        vec3 p = ro + rd * t;
        vec3 normal = calcNormal(p);
        color = lighting(p, rd, normal, material);
    } else {
        // Sky with sun
        float skyGrad = 0.5 + 0.5 * rd.y;
        color = mix(vec3(0.85, 0.9, 1.0), vec3(0.3, 0.6, 1.0), skyGrad);
        
        // Add sun
        vec3 sunDir = normalize(vec3(0.4, 0.8, -0.4));
        float sun = pow(max(0.0, dot(rd, sunDir)), 128.0);
        color += vec3(1.0, 0.9, 0.7) * sun * 2.0;
        
        // Add clouds
        vec2 cloudUV = rd.xz * 3.0 + iTime * 0.1;
        float cloudNoise = fbm(cloudUV) * fbm(cloudUV * 0.5);
        color = mix(color, vec3(0.9, 0.9, 0.95), cloudNoise * 0.3 * (1.0 - rd.y));
    }
    
    // Enhanced tone mapping and color grading
    color = color / (1.0 + color * 0.8);
    color = pow(color, vec3(1.0 / 2.2));
    
    // Add slight vignette
    vec2 vigUV = fragCoord / iResolution.xy;
    float vig = 1.0 - 0.3 * length(vigUV - 0.5);
    color *= vig;
    
    fragColor = vec4(color, 1.0);
}