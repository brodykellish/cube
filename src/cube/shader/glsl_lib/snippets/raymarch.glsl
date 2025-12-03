// Raymarching Utilities

// Forward declaration - must be defined by shader
float sceneSDF(vec3 p);

// Raymarch the scene
float raymarch(vec3 ro, vec3 rd, float maxDist) {
    float t = 0.0;

    for (int i = 0; i < 64; i++) {
        vec3 p = ro + rd * t;
        float d = sceneSDF(p);

        if (d < 0.001) {
            return t;
        }

        if (t > maxDist) {
            break;
        }

        t += d * 0.9;
    }

    return -1.0;
}

// Calculate normal at point
vec3 calcNormal(vec3 p) {
    float eps = 0.001;
    vec2 h = vec2(eps, 0.0);
    return normalize(vec3(
        sceneSDF(p + h.xyy) - sceneSDF(p - h.xyy),
        sceneSDF(p + h.yxy) - sceneSDF(p - h.yxy),
        sceneSDF(p + h.yyx) - sceneSDF(p - h.yyx)
    ));
}
