// Core utilities for geometric primitives

// === SDF Primitives ===
float sdSphere(vec3 p, float r) {
    return length(p) - r;
}

float sdBox(vec3 p, vec3 b) {
    vec3 q = abs(p) - b;
    return length(max(q, 0.0)) + min(max(q.x, max(q.y, q.z)), 0.0);
}

float sdPlane(vec3 p, vec3 n, float h) {
    return dot(p, n) + h;
}

float sdTorus(vec3 p, vec2 t) {
    vec2 q = vec2(length(p.xz) - t.x, p.y);
    return length(q) - t.y;
}

float sdCylinder(vec3 p, float r, float h) {
    vec2 d = abs(vec2(length(p.xz), p.y)) - vec2(r, h);
    return min(max(d.x, d.y), 0.0) + length(max(d, 0.0));
}

// === Raymarching ===
// Forward declaration - will be defined by the shader
float sceneSDF(vec3 p);

float raymarch(vec3 ro, vec3 rd, float maxDist) {
    float t = 0.0;
    for (int i = 0; i < 80; i++) {
        vec3 p = ro + rd * t;
        float d = sceneSDF(p);
        if (d < 0.001 || t > maxDist) break;
        t += d * 0.9;
    }
    return (t > maxDist) ? -1.0 : t;
}

vec3 calcNormal(vec3 p) {
    const float eps = 0.001;
    const vec2 h = vec2(eps, 0.0);
    return normalize(vec3(
        sceneSDF(p + h.xyy) - sceneSDF(p - h.xyy),
        sceneSDF(p + h.yxy) - sceneSDF(p - h.yxy),
        sceneSDF(p + h.yyx) - sceneSDF(p - h.yyx)
    ));
}

// === Texturing ===
// UV coordinate generation for different primitives

// Sphere UV mapping
vec2 getSphereUV(vec3 p) {
    // Convert to spherical coordinates
    vec3 n = normalize(p);
    float theta = atan(n.z, n.x); // -pi to pi
    float phi = asin(n.y); // -pi/2 to pi/2

    // Map to 0-1 range
    vec2 uv;
    uv.x = (theta + 3.14159265) / (2.0 * 3.14159265);
    uv.y = (phi + 1.5707963) / 3.14159265;

    return uv;
}

// Box UV mapping (assumes box centered at origin)
vec2 getBoxUV(vec3 p, vec3 normal) {
    vec2 uv;

    // Determine which face we're on and get appropriate UVs
    if (abs(normal.y) > 0.9) {
        // Top/bottom faces
        uv = p.xz;
    } else if (abs(normal.x) > 0.9) {
        // Left/right faces
        uv = p.zy;
    } else {
        // Front/back faces
        uv = p.xy;
    }

    return uv;
}

// Torus UV mapping
vec2 getTorusUV(vec3 p, float majorRadius) {
    // Project to XZ plane to find angle around major circle
    float theta = atan(p.z, p.x);

    // Find the point on the major circle
    vec2 majorPoint = vec2(cos(theta), sin(theta)) * majorRadius;

    // Vector from major circle point to surface point
    vec3 toSurface = p - vec3(majorPoint.x, 0.0, majorPoint.y);

    // Angle around minor circle
    float phi = atan(toSurface.y, length(toSurface.xz) - majorRadius);

    // Map to UV coordinates
    vec2 uv;
    uv.x = (theta + 3.14159265) / (2.0 * 3.14159265);
    uv.y = (phi + 3.14159265) / (2.0 * 3.14159265);

    return uv;
}

// Plane UV mapping (infinite plane at y=0)
vec2 getPlaneUV(vec3 p) {
    // Simple XZ mapping for horizontal plane
    return p.xz;
}

// Checkerboard pattern
float checkerboard(vec2 uv, float scale) {
    vec2 grid = floor(uv * scale);
    return mod(grid.x + grid.y, 2.0);
}

// === Lighting ===
vec3 simpleLighting(vec3 p, vec3 rd, vec3 normal, vec3 color) {
    vec3 lightPos = vec3(4.0 * sin(iTime * 0.5), 3.0, 4.0 * cos(iTime * 0.5));
    vec3 lightDir = normalize(lightPos - p);

    float diff = max(dot(normal, lightDir), 0.0);
    vec3 reflectDir = reflect(-lightDir, normal);
    float spec = pow(max(dot(-rd, reflectDir), 0.0), 32.0);

    vec3 ambient = color * 0.2;
    vec3 diffuse = color * diff * 0.7;
    vec3 specular = vec3(1.0) * spec * 0.5;

    return ambient + diffuse + specular;
}

// === Debug Axes ===
// SDF for a cylinder (for axis lines)
float sdCylinder(vec3 p, vec3 a, vec3 b, float r) {
    vec3 pa = p - a;
    vec3 ba = b - a;
    float h = clamp(dot(pa, ba) / dot(ba, ba), 0.0, 1.0);
    return length(pa - ba * h) - r;
}

// SDF for a cone (for arrow heads)
float sdCone(vec3 p, vec3 pos, vec3 dir, float h, float r) {
    vec3 q = p - pos;
    // Align cone with direction
    vec3 up = abs(dir.y) < 0.999 ? vec3(0.0, 1.0, 0.0) : vec3(1.0, 0.0, 0.0);
    vec3 right = normalize(cross(up, dir));
    up = cross(dir, right);
    mat3 m = mat3(right, up, dir);
    q = q * m; // Transform to cone space

    // Cone SDF
    vec2 c = normalize(vec2(h, r));
    float d1 = -q.z;
    float d2 = max(dot(vec2(length(q.xy), q.z), c), -h);
    return length(max(vec2(d1, d2), 0.0)) + min(max(d1, d2), 0.0);
}

// Combine axis geometry (line + arrow)
float sdAxis(vec3 p, vec3 axis, float length, float thickness) {
    vec3 end = axis * length;
    vec3 arrowBase = axis * (length - 0.15);

    // Axis line
    float line = sdCylinder(p, vec3(0.0), arrowBase, thickness);

    // Arrow head (cone)
    float arrow = sdCone(p, arrowBase, axis, 0.15, thickness * 3.0);

    return min(line, arrow);
}

// All three axes combined
float sdDebugAxes(vec3 p, float scale) {
    float thickness = 0.01 * scale;
    float length = 0.7 * scale; // 70% of screen

    // X axis (red)
    float xAxis = sdAxis(p, vec3(1.0, 0.0, 0.0), length, thickness);

    // Y axis (green)
    float yAxis = sdAxis(p, vec3(0.0, 1.0, 0.0), length, thickness);

    // Z axis (blue)
    float zAxis = sdAxis(p, vec3(0.0, 0.0, 1.0), length, thickness);

    return min(min(xAxis, yAxis), zAxis);
}

// Get axis color based on which axis is closest
vec3 getAxisColor(vec3 p, float scale) {
    float thickness = 0.01 * scale;
    float length = 0.7 * scale;

    float xDist = sdAxis(p, vec3(1.0, 0.0, 0.0), length, thickness);
    float yDist = sdAxis(p, vec3(0.0, 1.0, 0.0), length, thickness);
    float zDist = sdAxis(p, vec3(0.0, 0.0, 1.0), length, thickness);

    if (xDist <= yDist && xDist <= zDist) {
        return vec3(1.0, 0.2, 0.2); // Red for X
    } else if (yDist <= zDist) {
        return vec3(0.2, 1.0, 0.2); // Green for Y
    } else {
        return vec3(0.2, 0.2, 1.0); // Blue for Z
    }
}

