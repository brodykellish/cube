// Photorealistic happy woman face with expression control - Enhanced Contrast
// iParam0 = smile intensity (0.0 = frown, 1.0 = big smile)
// iParam1 = eye brightness/openness
// iParam2 = skin tone warmth
// iParam3 = lighting intensity

// === Noise Functions ===
float hash(vec2 p) {
    return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

float noise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    
    float a = hash(i);
    float b = hash(i + vec2(1.0, 0.0));
    float c = hash(i + vec2(0.0, 1.0));
    float d = hash(i + vec2(1.0, 1.0));
    
    return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}

float fbm(vec2 p) {
    float value = 0.0;
    float amplitude = 0.5;
    for(int i = 0; i < 4; i++) {
        value += amplitude * noise(p);
        p *= 2.0;
        amplitude *= 0.5;
    }
    return value;
}

// === SDF Functions ===
float sdSphere(vec3 p, float r) {
    return length(p) - r;
}

float sdEllipsoid(vec3 p, vec3 r) {
    float k0 = length(p / r);
    float k1 = length(p / (r * r));
    return k0 * (k0 - 1.0) / k1;
}

float sdCapsule(vec3 p, vec3 a, vec3 b, float r) {
    vec3 pa = p - a, ba = b - a;
    float h = clamp(dot(pa, ba) / dot(ba, ba), 0.0, 1.0);
    return length(pa - ba * h) - r;
}

float smin(float a, float b, float k) {
    float h = max(k - abs(a - b), 0.0);
    return min(a, b) - h * h * 0.25 / k;
}

float smax(float a, float b, float k) {
    float h = max(k - abs(a - b), 0.0);
    return max(a, b) + h * h * 0.25 / k;
}

// === Face Construction ===
float faceSDF(vec3 p) {
    vec3 op = p;
    
    // Basic head shape - slightly elongated sphere
    float head = sdEllipsoid(p, vec3(0.8, 1.0, 0.7));
    
    // Eye sockets
    vec3 eyeL = p - vec3(-0.25, 0.15, 0.45);
    vec3 eyeR = p - vec3(0.25, 0.15, 0.45);
    float eyeSocketL = sdSphere(eyeL, 0.2);
    float eyeSocketR = sdSphere(eyeR, 0.2);
    
    // Nose
    vec3 noseP = p - vec3(0.0, -0.1, 0.5);
    float nose = sdEllipsoid(noseP, vec3(0.08, 0.15, 0.12));
    
    // Mouth area depression
    float smileAmount = mix(-0.3, 0.3, iParam0); // Control smile vs frown
    vec3 mouthP = p - vec3(0.0, -0.4 + smileAmount * 0.1, 0.4);
    float mouthDepth = sdEllipsoid(mouthP, vec3(0.25, 0.08, 0.1));
    
    // Combine features
    head = smax(head, -eyeSocketL * 0.5, 0.1);
    head = smax(head, -eyeSocketR * 0.5, 0.1);
    head = smin(head, nose, 0.15);
    head = smax(head, -mouthDepth * 0.3, 0.08);
    
    return head;
}

float eyesSDF(vec3 p) {
    float eyeBrightness = mix(0.5, 1.0, iParam1);
    
    // Left eye
    vec3 eyeLPos = p - vec3(-0.25, 0.15, 0.52);
    float eyeL = sdSphere(eyeLPos, 0.08 * eyeBrightness);
    
    // Right eye  
    vec3 eyeRPos = p - vec3(0.25, 0.15, 0.52);
    float eyeR = sdSphere(eyeRPos, 0.08 * eyeBrightness);
    
    return min(eyeL, eyeR);
}

float lipsSDF(vec3 p) {
    float smileAmount = mix(-0.2, 0.2, iParam0);
    
    // Upper lip
    vec3 upperLipP = p - vec3(0.0, -0.35 + smileAmount, 0.48);
    float upperLip = sdEllipsoid(upperLipP, vec3(0.15, 0.03, 0.05));
    
    // Lower lip
    vec3 lowerLipP = p - vec3(0.0, -0.42 + smileAmount, 0.47);
    float lowerLip = sdEllipsoid(lowerLipP, vec3(0.15, 0.04, 0.06));
    
    return min(upperLip, lowerLip);
}

// === Scene SDF ===
float sceneSDF(vec3 p) {
    return faceSDF(p);
}

// === Raymarching ===
float raymarch(vec3 ro, vec3 rd, float maxDist) {
    float t = 0.0;
    for(int i = 0; i < 128; i++) {
        vec3 p = ro + rd * t;
        float d = sceneSDF(p);
        if(d < 0.001) return t;
        if(t > maxDist) break;
        t += d * 0.7;
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

// === Enhanced contrast function ===
vec3 enhanceContrast(vec3 color, float contrast) {
    // Enhance contrast by expanding the range around mid-gray
    vec3 midpoint = vec3(0.5);
    return midpoint + (color - midpoint) * contrast;
}

// === Material and Lighting ===
vec3 getSkinColor(vec3 p, vec3 normal) {
    float warmth = mix(0.3, 0.8, iParam2);
    
    // Base skin tone with enhanced contrast range
    vec3 skinBase = mix(
        vec3(0.92, 0.75, 0.65),  // Darker cool skin for higher contrast
        vec3(1.0, 0.88, 0.78),   // Brighter warm skin for higher contrast
        warmth
    );
    
    // Add more pronounced skin texture for contrast
    float skinNoise = fbm(p.xy * 50.0) * 0.15; // Increased from 0.1
    skinBase += skinNoise * 0.08; // Increased from 0.05
    
    // Enhanced blush on cheeks
    float smileAmount = iParam0;
    vec3 leftCheek = p - vec3(-0.3, 0.0, 0.3);
    vec3 rightCheek = p - vec3(0.3, 0.0, 0.3);
    float cheekBlush = exp(-length(leftCheek) * 8.0) + exp(-length(rightCheek) * 8.0);
    skinBase += vec3(0.3, 0.08, 0.08) * cheekBlush * smileAmount; // Increased contrast
    
    return skinBase;
}

vec3 getEyeColor(vec3 p) {
    // Enhanced contrast eyes
    vec3 eyeLPos = p - vec3(-0.25, 0.15, 0.52);
    vec3 eyeRPos = p - vec3(0.25, 0.15, 0.52);
    
    float leftDist = length(eyeLPos);
    float rightDist = length(eyeRPos);
    
    if(leftDist < 0.08 || rightDist < 0.08) {
        float pupilSize = 0.03;
        if(leftDist < pupilSize || rightDist < pupilSize) {
            return vec3(0.0); // Deep black pupil for high contrast
        }
        return vec3(0.4, 0.2, 0.08); // More saturated brown iris
    }
    
    return vec3(1.0); // Bright white sclera
}

vec3 getLipColor(vec3 p) {
    vec3 upperLipP = p - vec3(0.0, -0.35 + mix(-0.2, 0.2, iParam0), 0.48);
    vec3 lowerLipP = p - vec3(0.0, -0.42 + mix(-0.2, 0.2, iParam0), 0.47);
    
    if(length(upperLipP) < 0.15 || length(lowerLipP) < 0.15) {
        return vec3(0.9, 0.3, 0.3); // More saturated lips for higher contrast
    }
    
    return vec3(1.0);
}

vec3 lighting(vec3 p, vec3 rd, vec3 normal) {
    float lightIntensity = mix(0.8, 1.5, iParam3); // Increased range for higher contrast
    
    // Enhanced key light (stronger main facial lighting)
    vec3 keyLight = normalize(vec3(0.5, 1.0, 1.0));
    float keyDiff = max(dot(normal, keyLight), 0.0);
    keyDiff = pow(keyDiff, 0.8); // Enhance the contrast curve
    
    // Reduced fill light for more dramatic shadows
    vec3 fillLight = normalize(vec3(-0.3, 0.5, 0.8));
    float fillDiff = max(dot(normal, fillLight), 0.0) * 0.3; // Reduced from 0.5
    
    // Enhanced rim light
    vec3 rimLight = normalize(vec3(0.0, 0.3, -1.0));
    float rimDiff = pow(max(dot(normal, rimLight), 0.0), 1.5) * 0.5; // Enhanced rim
    
    // Stronger specular highlight
    vec3 reflectDir = reflect(-keyLight, normal);
    float spec = pow(max(dot(-rd, reflectDir), 0.0), 64.0) * 0.4; // Sharper, brighter specular
    
    // Get material colors
    vec3 skinColor = getSkinColor(p, normal);
    vec3 eyeColor = getEyeColor(p);
    vec3 lipColor = getLipColor(p);
    
    // Combine material colors
    vec3 materialColor = skinColor;
    if(eyeColor != vec3(1.0)) materialColor = eyeColor;
    if(lipColor != vec3(1.0)) materialColor = lipColor;
    
    // Reduced ambient for deeper shadows
    vec3 ambient = materialColor * 0.15; // Reduced from 0.3
    
    // Enhanced diffuse with higher contrast
    vec3 diffuse = materialColor * (keyDiff * 0.9 + fillDiff * 0.2) * lightIntensity;
    
    // Enhanced rim lighting
    vec3 rim = materialColor * rimDiff * 0.6; // Increased from 0.4
    
    // Brighter specular
    vec3 specular = vec3(1.0) * spec;
    
    vec3 finalColor = ambient + diffuse + rim + specular;
    
    // Apply additional contrast enhancement
    finalColor = enhanceContrast(finalColor, 1.4); // 40% contrast boost
    
    return finalColor;
}

// === Main Shader ===
void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = (fragCoord - 0.5 * iResolution.xy) / iResolution.y;
    
    // Camera setup
    vec3 ro = iCameraPos;
    vec3 rd = normalize(uv.x * iCameraRight + uv.y * iCameraUp + iCameraForward);
    
    // Black background
    vec3 color = vec3(0.0, 0.0, 0.0);
    
    // Raymarch
    float t = raymarch(ro, rd, 20.0);
    
    if(t > 0.0) {
        vec3 p = ro + rd * t;
        vec3 normal = calcNormal(p);
        
        // Apply lighting
        color = lighting(p, rd, normal);
        
        // Atmospheric perspective (reduced for black background)
        float fog = 1.0 - exp(-t * 0.1);
        vec3 fogColor = vec3(0.0, 0.0, 0.0); // Black fog for black background
        color = mix(color, fogColor, fog * 0.05); // Further reduced fog effect for higher contrast
    }
    
    // Enhanced gamma correction for more contrast
    color = pow(color, vec3(1.0 / 2.0)); // Slightly higher gamma for more punch
    
    // Final contrast adjustment
    color = clamp(color, 0.0, 1.0);
    
    fragColor = vec4(color, 1.0);
}