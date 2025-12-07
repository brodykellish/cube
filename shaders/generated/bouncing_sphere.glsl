// Bouncing sphere with random color effects
// iParam0: Bounce height (0.0 = low bounce, 1.0 = high bounce)
// iParam1: Bounce speed (0.0 = slow, 1.0 = fast)
// iParam2: Color change speed (0.0 = slow, 1.0 = fast)
// iParam3: Color chaos intensity (0.0 = smooth, 1.0 = chaotic)

// === SDF ===
float sdSphere(vec3 p, float radius) {
    return length(p) - radius;
}

float sdGround(vec3 p) {
    return p.y + 2.0;
}

// === Noise Functions ===
float hash(float n) {
    return fract(sin(n) * 43758.5453);
}

float noise(vec3 p) {
    vec3 i = floor(p);
    vec3 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    
    float n = i.x + i.y * 57.0 + i.z * 113.0;
    return mix(mix(mix(hash(n), hash(n + 1.0), f.x),
                   mix(hash(n + 57.0), hash(n + 58.0), f.x), f.y),
               mix(mix(hash(n + 113.0), hash(n + 114.0), f.x),
                   mix(hash(n + 170.0), hash(n + 171.0), f.x), f.y), f.z);
}

// === Physics Simulation ===
float getBounceHeight(float time, float speed, float maxHeight) {
    float period = 2.0 / speed;
    float t = mod(time, period) / period;
    
    // Parabolic bounce trajectory
    float bounce = 4.0 * t * (1.0 - t);
    return bounce * maxHeight;
}

// === Scene SDF ===
float sceneSDF(vec3 p) {
    float bounceSpeed = 0.5 + iParam1 * 3.0;
    float maxHeight = 1.0 + iParam0 * 4.0;
    
    // Calculate sphere position
    float bounceY = getBounceHeight(iTime, bounceSpeed, maxHeight);
    vec3 spherePos = vec3(0.0, bounceY - 1.5, 0.0);
    
    float sphere = sdSphere(p - spherePos, 0.5);
    float ground = sdGround(p);
    
    return min(sphere, ground);
}

// === Raymarching ===
float raymarch(vec3 ro, vec3 rd, float maxDist) {
    float t = 0.0;
    for (int i = 0; i < 80; i++) {
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

// === Color Generation ===
vec3 getRandomColor(float time, vec3 pos) {
    float colorSpeed = 0.5 + iParam2 * 3.0;
    float chaos = iParam3;
    
    // Base time-based colors
    float r = sin(time * colorSpeed + pos.x * chaos * 10.0) * 0.5 + 0.5;
    float g = sin(time * colorSpeed * 1.3 + pos.y * chaos * 10.0 + 2.0) * 0.5 + 0.5;
    float b = sin(time * colorSpeed * 0.8 + pos.z * chaos * 10.0 + 4.0) * 0.5 + 0.5;
    
    // Add noise for chaos
    if (chaos > 0.1) {
        vec3 noiseInput = pos * 5.0 + time * colorSpeed;
        float n1 = noise(noiseInput);
        float n2 = noise(noiseInput + vec3(100.0));
        float n3 = noise(noiseInput + vec3(200.0));
        
        r = mix(r, n1, chaos * 0.8);
        g = mix(g, n2, chaos * 0.8);
        b = mix(b, n3, chaos * 0.8);
    }
    
    // Ensure colors are vibrant
    vec3 color = vec3(r, g, b);
    color = pow(color, vec3(0.8)); // Increase brightness
    color = mix(color, vec3(1.0), 0.1); // Add slight white tint
    
    return color;
}

// === Lighting ===
vec3 lighting(vec3 p, vec3 rd, vec3 normal, vec3 color) {
    // Multiple light sources for dynamic lighting
    vec3 lightPos1 = vec3(3.0 * sin(iTime * 0.7), 4.0, 3.0 * cos(iTime * 0.7));
    vec3 lightPos2 = vec3(-2.0 * cos(iTime * 1.1), 3.0, 2.0 * sin(iTime * 1.1));
    
    vec3 lightDir1 = normalize(lightPos1 - p);
    vec3 lightDir2 = normalize(lightPos2 - p);
    
    // Diffuse lighting
    float diff1 = max(dot(normal, lightDir1), 0.0);
    float diff2 = max(dot(normal, lightDir2), 0.0);
    
    // Specular lighting
    vec3 viewDir = -rd;
    vec3 reflectDir1 = reflect(-lightDir1, normal);
    vec3 reflectDir2 = reflect(-lightDir2, normal);
    float spec1 = pow(max(dot(viewDir, reflectDir1), 0.0), 32.0);
    float spec2 = pow(max(dot(viewDir, reflectDir2), 0.0), 16.0);
    
    // Combine lighting
    vec3 ambient = color * 0.3;
    vec3 diffuse = color * (diff1 * 0.6 + diff2 * 0.4);
    vec3 specular = vec3(1.0) * (spec1 * 0.5 + spec2 * 0.3);
    
    return ambient + diffuse + specular;
}

// === Material Detection ===
int getMaterial(vec3 p) {
    float bounceSpeed = 0.5 + iParam1 * 3.0;
    float maxHeight = 1.0 + iParam0 * 4.0;
    
    float bounceY = getBounceHeight(iTime, bounceSpeed, maxHeight);
    vec3 spherePos = vec3(0.0, bounceY - 1.5, 0.0);
    
    float sphere = sdSphere(p - spherePos, 0.5);
    float ground = sdGround(p);
    
    return (sphere < ground) ? 0 : 1; // 0 = sphere, 1 = ground
}

// === Main Shader ===
void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = (fragCoord - 0.5 * iResolution.xy) / iResolution.y;
    
    vec3 ro = iCameraPos;
    vec3 rd = normalize(uv.x * iCameraRight + uv.y * iCameraUp + iCameraForward);
    
    float t = raymarch(ro, rd, 30.0);
    
    vec3 col = vec3(0.02, 0.02, 0.1); // Background color
    
    if (t > 0.0) {
        vec3 p = ro + rd * t;
        vec3 normal = calcNormal(p);
        int material = getMaterial(p);
        
        vec3 matColor;
        if (material == 0) {
            // Sphere - random colors
            matColor = getRandomColor(iTime, p);
        } else {
            // Ground - simple checkerboard
            vec2 groundUV = p.xz * 2.0;
            float checker = mod(floor(groundUV.x) + floor(groundUV.z), 2.0);
            matColor = mix(vec3(0.1), vec3(0.3), checker);
        }
        
        col = lighting(p, rd, normal, matColor);
        
        // Add glow effect around sphere
        if (material == 0) {
            float glow = 1.0 / (1.0 + t * t * 0.1);
            col += getRandomColor(iTime, p) * glow * 0.2;
        }
    }
    
    // Add some atmospheric perspective
    col = mix(col, vec3(0.02, 0.02, 0.1), smoothstep(0.0, 30.0, t));
    
    // Tone mapping and gamma correction
    col = col / (1.0 + col);
    col = pow(col, vec3(1.0 / 2.2));
    
    fragColor = vec4(col, 1.0);
}