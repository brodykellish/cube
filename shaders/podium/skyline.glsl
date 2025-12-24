#define S(a,b,t) smoothstep(a,b,t)

float Box(vec2 p, vec2 xy, float w, float h, float blur)
{
    float b = S(blur, -blur, -p.x-xy.x) * S(-blur, blur, -p.x+w-xy.x);
    b *= S(blur, -blur, -p.y-xy.y) * S(-blur, blur, -p.y+h-xy.y);
    return b;
}

float Arc(vec2 uv, vec2 pos, float inner, float outer, float arcAngle, float angle)
{
    vec2 p = mat2x2(cos(angle), -sin(angle), sin(angle), cos(angle))*(uv - pos);
    float l = length(p);
    float a = atan(p.x, p.y)+3.14;
    float circle = -S(outer-.001, outer+.001, l) + S(inner-.001, inner+.001, l);
    float arc = circle * S(arcAngle+.001, arcAngle-.001, a);
    
    return arc;
}

float TaperBox(vec2 p, float wb, float wt, float yb, float yt, float blur)
{
    float m = S(-blur, blur, p.y-yb);
    m *= S(blur, -blur, p.y-yt);
    
    p.x = abs(p.x);
    float w = mix(wb, wt, (p.y-yb)/(yt-yb));
    m *= S(blur, -blur, p.x-w);
    return m;
}

vec4 Sun(vec2 uv)
{
    float circle = S(1.001, 1., length(uv));
    float bands = S(-.5, .5, sin(-uv.y*50.+iTime));
    
    vec3 col = mix(vec3(1., .5, 0.), vec3(1., 1., 0.), uv.y) * circle;
    
    
    return vec4(col, circle*bands);
}

vec4 Buildings(vec2 uv, float color_factor)
{
    // Building position IDs
    float id = floor(uv.x);
    uv.x = fract(uv.x);
    
    // Random, quantized building heights
    float height = floor((sin(id*13448.15)*.5+.5)*7.)+1.;
    float col_factor = fract((sin(id*id*123.15)*.2+.2))*color_factor;
    float col = Box(uv, vec2(0), 1.1, height, .001);
    
    // Building lights
    vec2 uv_lights = uv * 4.;
    vec2 light_id = floor(uv_lights);
    uv_lights = fract(uv_lights+.75);
    float light = step(.5, fract(sin((light_id.x+id)*47.12)*cos((light_id.y-id)*78.24)*182.457));
    float lights = Box(uv_lights, vec2(0), .5, .5, 0.1) * light;
    
    vec3 base_color = vec3(col_factor, col_factor, col_factor);
    vec3 light_color = vec3(1., 1., 0.);
    vec3 final_color = mix(base_color, light_color, lights);
    
    return vec4(final_color * col, col);
}

vec4 Waves(vec2 uv, float offset, vec3 color)
{
    vec2 uv_dots = uv*5.;
    uv *= 5.;
    uv += vec2(sin(iTime+offset)*5., cos(iTime+offset)*5.);
    
    float dist_water = max(0., uv.y+1.8) * max(0.,uv.y+1.8);
    float dist_foam = max(0., uv.y+2.8) * max(0.,uv.y+2.8);
    vec2 uv_water = uv - vec2(dist_water*.4, 0);
    vec2 uv_foam = uv - vec2(dist_foam*.4, 0);
    
    float xsin_foam = sin(uv_water.x);
    float xsin_water = sin(uv_foam.x);
    
    float foam = S(uv.y-.1, uv.y+.1, xsin_foam);
    float water = S(uv.y+1.9, uv.y+2.1, xsin_water);
    
    uv_dots = fract(uv_dots*.5 + vec2(iTime*10., 0.))-.5;
    float dots = 1.-S(.01, .2, length(uv_dots));
    
    vec3 col = vec3(foam - water + water*color + dots*water);
    float alpha = max(foam, water);
    
    return vec4(col, alpha);
}

vec4 Road(vec2 uv)
{
    float all_ground = S(-.37, -.3701, uv.y);
    
    vec2 uv_bands = vec2(fract(uv.x*2.), uv.y);
    float bands = Box(uv_bands, vec2(.0, .45), .3, .02, .001);
    float ground = all_ground - bands;
    
    vec3 col = ground*vec3(.3, .3, .3) + bands*vec3(0.9, 0.9, 0.0);
    
    float pavement_straight = S(-.34, -.3401, uv.y) * S(-.3701, -.37, uv.y);
    col += pavement_straight*vec3(.4, .4, .4)*step(-.995, sin(uv.x*60.));
    
    vec2 uv_persp = mat2x2(.7071, .7071, -.7071, .7071)*uv;
    float pavement_persp = S(-.25, -.251, uv.y) * S(-.3401, -.34, uv.y);
    col += pavement_persp*vec3(.5, .5, .5)*step(-.995, sin(uv_persp.x*84.852-1.6)) * step(-.995, sin(uv.y*200.0+4.));
    
    return vec4(col, max(all_ground, max(bands, max(pavement_straight, pavement_persp))));
}

vec4 Lights(vec2 uv)
{
    uv.x = fract(uv.x/5.)*5.-.4;
    float base = TaperBox(uv, .02, .01, -0.2, -0.09, 0.001);
    float pole = Box(uv, vec2(.01, .1), .02, .5, .001);
    float lamp_arc = Arc(uv, vec2(-.06, .395), .05, .07, 1.571, 3.141);
    float bar = Box(uv, vec2(.149, -.445), .09, .02, .001);
    float lightcap = S(.001, -.001, length(uv*vec2(.5, 1.) - vec2(-.1, .45)) - .03);
    float bulb = S(.001, -.001, length(uv*vec2(.7, 1.4) - vec2(-.14, .61)) - .03);
    float light = TaperBox(uv + vec2(.2, .37), .1, .03, -.1, .8, 0.02) * .8;
    float light_present = step(0.01, light);
    
    float gray_elements = max(base, max(pole, max(lamp_arc, max(bar, lightcap))));
    
    vec3 color = gray_elements*vec3(.4) + bulb*vec3(1.) + light_present*vec3(1., 1., .0);
    
    return vec4(color, max(gray_elements, max(bulb, light)));
}

vec2 IntersectionY(vec2 b, vec2 a, vec2 d, vec2 c)
{
    float s = (a.x * d.y) / (a.y*c.x - a.x*c.y);
    return vec2(c.x*s + d.x, c.y*s + d.y);
}

vec4 Tower(vec2 uv)
{
    uv.x = fract(uv.x/80.)*80.-20.;
    
    // Tower extremes (normals and directions. All start at 0,0)
    vec2 n1 = vec2(cos(0.2), sin(0.2));
    vec2 n2 = vec2(cos(-0.2), sin(-0.2));
    vec2 l1 = vec2(-n1.y, n1.x);
    vec2 l2 = vec2(-n2.y, n2.x);
    vec2 p0 = vec2(0);
    
    // Starting point for scaffolding, and angles.
    vec2 ps = vec2(.0, -16.);
    
    vec2 s2 = vec2(cos(-0.6), sin(-0.6));
    vec2 s1 = vec2(cos(0.6), sin(0.6));
    vec2 sn1 = vec2(-s1.y, s1.x);
    vec2 sn2 = vec2(-s2.y, s2.x);

    // Debug lines drawn
    float d1 = S(.4, .3, abs(dot(uv, n1)));
    float d2 = S(.4, .3, abs(dot(uv, n2)));
    float line1 = 0.0, line2 = 0.0;
    
    vec4 scaffold_col;
    vec4 col;
    
    // Start reflecting line
    vec2 y = IntersectionY(p0, l2, ps, s2);
    line1 = S(.2, .1, abs(dot(uv-ps, sn2)));
    scaffold_col = vec4(line1 * vec3(1.0, 0.0, 0.0), line1);
    
    for (float i = 0.; i < 1.; i+=1./3.)
    {
        float wi = mix(.2, .01, i);
        y = 2.*IntersectionY(p0, l1, y, s1) - y;
        line1 = S(wi, wi/2., abs(dot(uv-y, sn1)));
        col = vec4(line1 * vec3(1.0), line1);
        scaffold_col = mix(scaffold_col, col, col.a);
        
        y = 2.*IntersectionY(p0, l2, y, s2) - y;
        line1 = S(wi, wi/2., abs(dot(uv-y, sn2)));
        col = vec4(line1 * vec3(1.0, 0.0, 0.0), line1);
        scaffold_col = mix(scaffold_col, col, col.a);
    }
    
    y = IntersectionY(p0, l1, ps, s1);
    line2 = S(.2, .1, abs(dot(uv-ps, sn1)));
    col = vec4(line2 * vec3(1.0, 0.0, 0.0), line2);
    scaffold_col = mix(scaffold_col, col, col.a);
    
    for (float i = 0.; i < 1.; i+=1./3.)
    {
        float wi = mix(.2, .01, i);
        y = 2.*IntersectionY(p0, l2, y, s2) - y;
        line2 = S(wi, wi/2., abs(dot(uv-y, sn2)));
        col = vec4(line2 * vec3(1.0), line2);
        scaffold_col = mix(scaffold_col, col, col.a);
        
        y = 2.*IntersectionY(p0, l1, y, s1) - y;
        line2 = S(wi, wi/2., abs(dot(uv-y, sn1)));
        col = vec4(line2 * vec3(1.0, 0.0, 0.0), line2);
        scaffold_col = mix(scaffold_col, col, col.a);
    }
    
    vec4 extremes_col = vec4(max(d1, d2) * vec3(.5, .5, .5), max(d1, d2));
    float mask = TaperBox(uv, 4.28, .0, -20., .0, 0.1);
    vec4 tower = mix(scaffold_col, extremes_col, extremes_col.a) * mask;
    
    float light = S(1., 0., length(uv) - .1);
    vec4 light_col = vec4(vec3(1.0, 0.0, 0.0), light*(sin(iTime)*.5+.5));
    
    return vec4(mix(tower, light_col, light_col.a));
}

void mainImage( out vec4 fragColor, in vec2 fragCoord )
{
    // Normalized pixel coordinates (from 0 to 1)
    vec2 uv = (fragCoord-.5*iResolution.xy)/iResolution.y;
    float t = iTime;
    
    // Background
    vec4 col = mix(vec4(1., 1., 0.0, 1.0), vec4(1.0, 0.0, 1.0, 1.0)*.7, uv.y*3.-.2);
    
    // Background sun
    vec4 sun = Sun(uv*3.);
    col = mix(col, sun, sun.a);
    
    // Towers
    vec4 tower = Tower(uv*40.+vec2(t, -15.));
    col = mix(col, tower, tower.a);
    
    // Buildings
    for (float i = 0.; i < 1.; i += .3)
    {
        float scale = mix(30., 20., i);
        vec4 buildings = Buildings(uv*scale+vec2(t+i*123.45,0.), i);
        col = mix(col, buildings, buildings.a);
    }

    // Waves
    for (float i = 0.; i < 1.; i += .1)
    {
        float scale = mix(40., 10., i);
        vec3 color = mix(vec3(.3, .3, 1.), vec3(.8, .8, 1.), i);
        vec4 waves = Waves(uv*scale+vec2(0.,i*3.-1.2), i*5., color);
        col = mix(col, waves, waves.a);
    }
    
    // Ground
    vec4 road = Road(uv+vec2(t, 0.));
    col = mix(col, road, road.a);
    
    // Lights
    vec4 lights = Lights(uv+vec2(t, .1));
    col = mix(col, lights, lights.a);
    
    // Output to screen
    fragColor = col;
}