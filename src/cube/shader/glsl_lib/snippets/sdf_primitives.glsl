// SDF Primitive Library
// Signed Distance Functions for basic geometric shapes

float sdSphere(vec3 p, float radius) {
    return length(p) - radius;
}

float sdBox(vec3 p, vec3 size) {
    vec3 q = abs(p) - size;
    return length(max(q, 0.0)) + min(max(q.x, max(q.y, q.z)), 0.0);
}

float sdTorus(vec3 p, vec2 t) {
    vec2 q = vec2(length(p.xz) - t.x, p.y);
    return length(q) - t.y;
}

float sdCylinder(vec3 p, float radius, float height) {
    vec2 d = abs(vec2(length(p.xz), p.y)) - vec2(radius, height);
    return min(max(d.x, d.y), 0.0) + length(max(d, 0.0));
}

float sdPlane(vec3 p, vec3 normal, float offset) {
    return dot(p, normal) + offset;
}
