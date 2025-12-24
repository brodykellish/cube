
#define T iTime
#define PI 3.1415926
#define TAU 6.283185
#define S smoothstep
#define s1(v) (sin(v)*.5+.5)
const float EPSILON = 1e-3;

mat2 rotate(float a){
  float s = sin(a);
  float c = cos(a);
  return mat2(c,-s,s,c);
}


float hash11(float p)
{
    p = fract(p * .1031);
    p *= p + 33.33;
    p *= p + p;
    return fract(p);
}

float noise(float v){
  float i = floor(v);
  float f = fract(v);
  float h1 = hash11(i);
  float h2 = hash11(i+1.);
  return mix(h1,h2,S(0.,1.,f));
}
float smin( float d1, float d2, float k )
{
    k *= 4.0;
    float h = max(k-abs(d1-d2),0.0);
    return min(d1, d2) - h*h*0.25/k;
}
void mainImage(out vec4 O, in vec2 I){
  vec2 R = iResolution.xy;
  vec2 uv = (I - 0.5 * R) / R.y;

  O.rgb *= 0.;
  O.a = 1.;

  // Use camera uniforms
  vec3 ro = iCameraPos;
  vec3 rd = normalize(uv.x * iCameraRight + uv.y * iCameraUp + iCameraForward);

  float z = .1;

  // iParam1 controls rotation speed (0-1 -> 0x-2x speed)
  float rotationSpeed = mix(0.0, -2.0, clamp(iParam4, 0.0, 1.0));
  mat2 mx = rotate(T * rotationSpeed);
  mat2 my = rotate(T * 0.0);

  vec3 col = vec3(0);
  vec3 C = vec3(3,2,1);
  float i=0.;

  float n = noise(T*1.);

  while(i++<80.){
    vec3 p = ro + rd * z;

    p.xz *= mx;
    p.yz *= my;
    

    vec3 q = p;
    float ang = atan(q.z, q.x);
    float dis = length(q);
    dis -= T*2.;
    ang = cos(ang*5.);
    dis = cos(dis*.5);
    dis += S(n+.2,n,dis);

    q.xz = vec2(ang, dis);
    q.y *= .3;

    float d = length(q) - 1.;

    {
      float d1 = length(p) - 2.;
      d = smin(d, d1, .3);
    }
    
    {
      float d1 = length(q.xz) - .2;
      d = smin(d, d1, .1);
    }

    d = abs(d)*.8 + .01;

    if(d<EPSILON) break;
    
    col += s1(C-T*4.+i*.1)/d;
    
    z += d;
  }

  col = tanh(col / 1300.);

  O.rgb = col;
}