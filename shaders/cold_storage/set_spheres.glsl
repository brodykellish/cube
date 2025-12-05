// Rotating spheres with MIDI-controlled speed and RGB colors
// iParam0: Rotation speed multiplier
// iParam1: Red color intensity
// iParam2: Green color intensity  
// iParam3: Blue color intensity

float sdSphere(vec3 p, float r) {
    return length(p) - r;
}

float sdUnion(float d1, float d2) {
    return min(d1, d2);
}

mat3 rotY(float a) {
    float c = cos(a);
    float s = sin(a);
    return mat3(
        c, 0, s,
        0, 1, 0,
        -s, 0, c
    );
}

float map(vec3 p) {
    float rotSpeed = iParam0 * 2.0 + 0.1; // Speed control (0.1 to 2.1)
    float t = iTime * rotSpeed;
    
    // Create 4 spheres positioned around origin
    float radius = 0.8;
    float distance = 3.0;
    
    vec3 pos1 = rotY(t) * vec3(distance, 0, 0);
    vec3 pos2 = rotY(t + 1.57) * vec3(distance, 0, 0); // +90 degrees
    vec3 pos3 = rotY(t + 3.14) * vec3(distance, 0, 0); // +180 degrees
    vec3 pos4 = rotY(t + 4.71) * vec3(distance, 0, 0); // +270 degrees
    
    float sphere1 = sdSphere(p - pos1, radius);
    float sphere2 = sdSphere(p - pos2, radius);
    float sphere3 = sdSphere(p - pos3, radius);
    float sphere4 = sdSphere(p - pos4, radius);
    
    return sdUnion(sdUnion(sphere1, sphere2), sdUnion(sphere3, sphere4));
}

vec3 calcNormal(vec3 p) {
    const float h = 0.001;
    const vec2 k = vec2(1, -1);
    return normalize(k.xyy * map(p + k.xyy * h) +
                     k.yyx * map(p + k.yyx * h) +
                     k.yxy * map(p + k.yxy * h) +
                     k.xxx * map(p + k.xxx * h));
}

float rayMarch(vec3 ro, vec3 rd) {
    float t = 0.0;
    for (int i = 0; i < 100; i++) {
        vec3 p = ro + t * rd;
        float d = map(p);
        if (d < 0.001) break;
        if (t > 50.0) return -1.0;
        t += d;
    }
    return t;
}

vec3 lighting(vec3 p, vec3 n, vec3 rd, vec3 lightDir, vec3 color) {
    // Ambient
    vec3 ambient = color * 0.2;
    
    // Diffuse
    float diff = max(dot(n, lightDir), 0.0);
    vec3 diffuse = color * diff * 0.8;
    
    // Specular
    vec3 reflectDir = reflect(-lightDir, n);
    float spec = pow(max(dot(-rd, reflectDir), 0.0), 32.0);
    vec3 specular = vec3(1.0) * spec * 0.3;
    
    return ambient + diffuse + specular;
}

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = (fragCoord - 0.5 * iResolution.xy) / iResolution.y;
    
    // Use camera uniforms for proper 3D navigation
    vec3 ro = iCameraPos;
    vec3 rd = normalize(uv.x * iCameraRight + uv.y * iCameraUp + iCameraForward);
    
    // RGB color controls from MIDI parameters
    vec3 baseColor = vec3(iParam1, iParam2, iParam3);
    // Ensure minimum brightness
    baseColor = max(baseColor, vec3(0.1));
    
    float t = rayMarch(ro, rd);
    
    vec3 color = vec3(0.0);
    
    if (t > 0.0) {
        vec3 p = ro + t * rd;
        vec3 n = calcNormal(p);
        
        // Dynamic light position
        vec3 lightDir = normalize(vec3(sin(iTime), 1.0, cos(iTime)));
        
        color = lighting(p, n, rd, lightDir, baseColor);
        
        // Add some glow effect
        float glow = 1.0 / (1.0 + t * t * 0.01);
        color += baseColor * glow * 0.1;
    } else {
        // Background gradient
        float gradient = smoothstep(-1.0, 1.0, uv.y);
        color = mix(vec3(0.1, 0.1, 0.2), vec3(0.0), gradient);
    }
    
    // Tone mapping
    color = color / (color + vec3(1.0));
    
    // Gamma correction
    color = pow(color, vec3(1.0/2.2));
    
    fragColor = vec4(color, 1.0);
}