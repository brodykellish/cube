// Beach waves with realistic wave motion and foam
// iParam0: Wave frequency (0.0 = slow, 1.0 = fast)
// iParam1: Wave height/amplitude
// iParam2: Foam intensity
// iParam3: Water color mix (blue to green)

#define PI 3.14159265359
#define TAU 6.28318530718

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

// Multiple overlapping Gerstner waves for realistic water surface
float waterHeight(vec3 p) {
    float waveFreq = 0.3 + iParam0 * 2.0; // Wave frequency controlled by iParam0
    float waveHeight = 0.3 + iParam1 * 1.2; // Wave amplitude controlled by iParam1
    float time = iTime;
    
    vec2 pos = p.xz;
    float height = 0.0;
    
    // Primary wave train moving toward shore
    height += gerstnerWave(pos, vec2(0, 1), waveHeight * 0.8, 4.0 / waveFreq, 1.0, time) * 0.6;
    
    // Secondary waves at slight angle
    height += gerstnerWave(pos, vec2(0.3, 1), waveHeight * 0.6, 2.5 / waveFreq, 0.8, time) * 0.4;
    
    // Tertiary smaller waves
    height += gerstnerWave(pos, vec2(-0.2, 1), waveHeight * 0.4, 1.8 / waveFreq, 0.6, time) * 0.3;
    
    // High frequency surface detail
    height += sin(pos.x * 3.0 * waveFreq - time * 4.0) * waveHeight * 0.1;
    height += sin(pos.y * 4.0 * waveFreq - time * 3.0 + pos.x * 0.5) * waveHeight * 0.08;
    
    // Add some ocean swell
    height += sin(pos.y * 0.2 - time * 0.5) * waveHeight * 0.4;
    
    return height;
}

// SDF for water surface
float waterSDF(vec3 p) {
    float height = waterHeight(p);
    
    // Add turbulence near the shore where waves break
    float shoreDistance = max(0.0, 8.0 - p.z);
    if (shoreDistance > 0.0) {
        // Breaking wave effect - water gets choppy near shore
        float breakingTurbulence = fbm(vec2(p.x * 1.5, p.z * 1.5 - iTime * 2.0)) * shoreDistance * 0.15;
        // Add vertical spray/splash effect
        float splash = sin(p.z * 2.0 - iTime * 3.0) * exp(-shoreDistance * 0.3) * 0.3;
        height += breakingTurbulence + splash;
    }
    
    return p.y - height;
}

// SDF for beach/sand with more realistic slope
float beachSDF(vec3 p) {
    // Gentle beach slope
    float beachSlope = -0.8 + p.z * 0.08;
    
    // Add sand ripples and texture
    float sandRipples = sin(p.x * 2.0) * 0.02 + sin(p.z * 3.0) * 0.015;
    float sandNoise = fbm(vec2(p.x * 0.8, p.z * 0.8)) * 0.1;
    
    float sandHeight = beachSlope + sandRipples + sandNoise;
    return p.y - sandHeight;
}

// Combined scene SDF
vec2 sceneSDF(vec3 p) {
    float water = waterSDF(p);
    float beach = beachSDF(p);
    
    if (water < beach) {
        return vec2(water, 1.0); // Water material
    } else {
        return vec2(beach, 2.0); // Sand material
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

// Enhanced foam calculation
float calculateFoam(vec3 p) {
    float shoreDistance = max(0.0, 10.0 - p.z);
    float waveHeight = waterHeight(p);
    
    // Foam appears where water is shallow and turbulent
    float foamFromShore = exp(-shoreDistance * 0.2) * 0.8;
    
    // Foam at wave crests
    float foamFromCrest = smoothstep(0.1, 0.4, waveHeight) * 0.6;
    
    // Animated foam texture
    vec2 foamUV = vec2(p.x * 2.0 + iTime * 0.5, p.z * 2.0 - iTime * 1.5);
    float foamNoise = fbm(foamUV) * fbm(foamUV * 2.0) * 0.7;
    
    return (foamFromShore + foamFromCrest) * foamNoise * iParam2;
}

// Lighting
vec3 lighting(vec3 p, vec3 rd, vec3 normal, float material) {
    vec3 lightDir = normalize(vec3(0.4, 0.8, -0.4));
    vec3 lightColor = vec3(1.0, 0.95, 0.85);
    
    // Enhanced ambient lighting
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
        
        // Apply lighting
        color = color * (ambient * 0.8 + diffuse * 0.9) + specular * 1.2;
        
        // Add depth-based transparency
        float depth = length(p - iCameraPos);
        float transparency = exp(-depth * 0.1);
        vec3 deepWaterColor = vec3(0.02, 0.1, 0.3);
        color = mix(deepWaterColor, color, transparency);
        
    } else if (material == 2.0) { // Sand
        vec3 sandColor = vec3(0.85, 0.75, 0.55);
        
        // Wet sand near water
        float wetness = exp(-(p.z - 5.0) * 0.3) * 0.8;
        vec3 wetSandColor = vec3(0.6, 0.5, 0.35);
        sandColor = mix(sandColor, wetSandColor, clamp(wetness, 0.0, 1.0));
        
        // Add sand texture variation
        float sandNoise = fbm(vec2(p.x * 4.0, p.z * 4.0));
        sandColor = mix(sandColor, vec3(0.9, 0.8, 0.65), sandNoise * 0.2);
        
        color = sandColor * (ambient + diffuse * 0.7) + specular * 0.05;
        
    } else { // Sky/background
        float skyGrad = 0.5 + 0.5 * rd.y;
        color = mix(vec3(0.85, 0.9, 1.0), vec3(0.3, 0.6, 1.0), skyGrad);
    }
    
    return color;
}

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    // Setup camera using Shadertoy camera uniforms
    vec2 uv = (fragCoord - 0.5 * iResolution.xy) / iResolution.y;
    
    vec3 ro = iCameraPos;
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
        
        // Add some clouds
        float cloudNoise = fbm(rd.xz * 3.0 + iTime * 0.1);
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