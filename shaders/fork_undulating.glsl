#define A 9. // amplitude
#define T (iTime/3e2)
#define H(a) (cos(radians(vec3(180, 90, 0))+(a)*6.2832)*.5+.5)  // hue

float map(vec3 u, float v, float time)
{
    float t = time, l = 5., f = 1e10, i = 0., y, z;
    u.xy = vec2(atan(u.x, u.y), length(u.xy));
    u.x += t*v*3.1416*.7;
    for (; i++<l;){
        vec3 p = u;
        y = round((p.y-i)/l)*l+i;
        p.x *= y;
        p.x -= y*y*t*3.1416;
        p.x -= round(p.x/6.2832)*6.2832;
        p.y -= y;
        z = cos(y*t*6.2832)*.5 +.5;
        f = min(f, max(length(p.xy), -p.z -z*A) -.1 -z*.2 -p.z/1e2);
    }
    return f;
}

void mainImage( out vec4 C, vec2 U )
{
    vec2 R = iResolution.xy, j;
    vec3 c = vec3(0), p, k;

    // Use precomputed camera vectors for keyboard navigation
    vec2 uv = (U - R * 0.5) / R.y;
    vec3 o = iCameraPos;
    vec3 u = normalize(uv.x * iCameraRight + uv.y * iCameraUp + 1.0 * iCameraForward);

    float smoothBass = texture(iChannel2, vec2(0.0)).r;

    const float WOBBLE_SPEED = 20.0;
    const float WOBBLE_AMOUNT = 0.2;

    float timeOffset = sin(T * WOBBLE_SPEED) * pow(smoothBass, 2.0) * WOBBLE_AMOUNT;

    float dynamicTime = T + timeOffset;
    
    float t = dynamicTime, v = -o.z/3., i = 0., d = i, s, f, z, r;
    bool b;
    for (; i++<70.;){
        p = u*d +o;
        p.xy /= v; r = length(p.xy); z = abs(1. -r*r); b = r < 1.;
        if (b) z = sqrt(z);
        p.xy /= z+1.; p.xy *= v;
        p.xy -= cos(p.z/8. +t*3e2 +vec2(0, 1.5708) +z/2.)*.2;
        s = map(p, v, t);
        r = length(p.xy); f = cos(round(r)*t*6.2832)*.5+.5;
        k = H(.2 -f/3. +t +p.z/2e2);
        if (b) k = 1.-k;
        c += min(exp(s/-.05), s) * (f+.01) * min(z, 1.) * sqrt(cos(r*6.2832)*.5 +.5) * k*k;
        if (s < 1e-3 || d > 1e3) break;
        d += s*clamp(z, .3, .9);
    }
    
    c += texture(iChannel0, (u*d +o).xy).rrr * vec3(0, .4, s)*s*z*.03;
    c += min(exp(-p.z -f*A)*z*k*.01/s, 1.);
    j = p.xy/v;
    c /= clamp(dot(j, j)*4., .04, 4.);
    C = vec4(exp(log(c)/2.2), 1);
}
