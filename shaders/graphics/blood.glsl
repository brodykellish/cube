// 2D Blood and Fire Effect - MIDI Parameter Controlled
#define T (iTime)

vec4 blood(vec2 u) {
    float i=0.,a=0.,d=0.,s=0.,t=.4*iTime;
    vec3  p;
    vec4 o = vec4(0);

    // iParam0 controls blood flow speed (0.1x to 2x)
    float bloodSpeed = 0.1 + iParam0 * 1.9;
    t *= bloodSpeed;

    // iParam1 controls blood intensity/viscosity (0.2x to 2x)
    float bloodViscosity = 0.2 + iParam1 * 1.8;

    for(o*=i; i++<64.;
        d += s = (.01 + abs(s) * .4) * bloodViscosity,
        o.r+=d/s)
        for (p = vec3(u * d, d + t),
            s = min(cos(p.z), 6. - length(p.xy)),
            a = .8; a < 16.; a += a)
            p += cos(t+p.yzx)*.2,
            s += abs(dot(sin(t+.2*p.z+p * a), .6+p-p)) / a;
    return o * 2e1;
}

vec4 fire(vec2 u) {
    float i=0., d=0., s=0., n=0.;
    vec3 p;
    vec4 o = vec4(0);

    // iParam2 controls fire turbulence (0.3x to 3x)
    float fireTurbulence = 0.3 + iParam2 * 2.7;
    
    // iParam3 controls fire color temperature (cooler to hotter)
    float fireTemp = 0.5 + iParam3 * 1.5;

    for(; i++<1e2; ) {
        p = vec3(u * d, d);
        p += cos(p.z+T+p.yzx*.5) * (.6 * fireTurbulence);
        s = 6.-length(p.xy);
        p.xy *= mat2(cos(.3*T*fireTurbulence+vec4(0,33,11,0)));
        for (n = 1.6; n < 32.; n += n )
            s -= abs(dot(sin( p.z + T + p*n ), vec3(1.12))) / n;
        d += s = .01 + abs(s)*.1;
        o += 1. / s;
    }
    
    // Adjust fire color based on temperature parameter
    vec4 fireColor = vec4(5*fireTemp, 2*fireTemp, 1, 1);
    return fireColor * o * o / d;
}

void mainImage(out vec4 o, in vec2 u) {
    float s=.1,d=0.,i=0.;
    vec3  p = iResolution;
    u = (u-p.xy/2.)/p.y;

    // Mix between fire and blood effects
    // When all params are 0, more fire; when high, more blood
    float mixRatio = 0.5 + (iParam0 + iParam1) * 0.2;
    mixRatio = clamp(mixRatio, 0.1, 0.95);

    o = mix(fire(u), blood(u), mixRatio);
    o = tanh(o / 5e5);
    
    // Global intensity control based on average of all params
    float globalIntensity = 0.7 + dot(iParams, vec4(0.25)) * 0.6;
    o *= globalIntensity;
}