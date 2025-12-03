// Lighting Utilities

// Simple phong-style lighting
vec3 phongLighting(vec3 p, vec3 rd, vec3 normal, vec3 lightPos, vec3 baseColor) {
    vec3 lightDir = normalize(lightPos - p);

    // Diffuse
    float diff = max(dot(normal, lightDir), 0.0);

    // Specular
    vec3 reflectDir = reflect(-lightDir, normal);
    float spec = pow(max(dot(-rd, reflectDir), 0.0), 32.0);

    // Combine
    vec3 ambient = baseColor * 0.2;
    vec3 diffuse = baseColor * diff * 0.7;
    vec3 specular = vec3(1.0) * spec * 0.5;

    return ambient + diffuse + specular;
}

// Basic lighting with fixed overhead light
vec3 basicLighting(vec3 normal, vec3 baseColor) {
    vec3 lightDir = normalize(vec3(0.5, 1.0, 0.3));
    float diff = max(dot(normal, lightDir), 0.0);

    vec3 ambient = baseColor * 0.3;
    vec3 diffuse = baseColor * diff * 0.7;

    return ambient + diffuse;
}
