#define T iTime
#define PI 3.141596
#define TAU 6.283185
#define S smoothstep
#define s1(v) (sin(v)*.5+.5)

#define allowRotate

const float EPSILON = 1e-3;

mat2 rotate(float a){
  float s = sin(a);
  float c = cos(a);
  return mat2(c,-s,s,c);
}




// iq's sdf function
float sdBoxFrame( vec3 p, vec3 b, float e )
{
       p = abs(p  )-b;
  vec3 q = abs(p+e)-e;
  return min(min(
      length(max(vec3(p.x,q.y,q.z),0.0))+min(max(p.x,max(q.y,q.z)),0.0),
      length(max(vec3(q.x,p.y,q.z),0.0))+min(max(q.x,max(p.y,q.z)),0.0)),
      length(max(vec3(q.x,q.y,p.z),0.0))+min(max(q.x,max(q.y,p.z)),0.0));
}
void mainImage(out vec4 O, in vec2 I){
  vec2 R = iResolution.xy;
  vec2 uv = (I - R * 0.5) / R.y;

  O.rgb *= 0.;
  O.a = 1.;

  // Use precomputed camera vectors for keyboard navigation
  vec3 ro = iCameraPos;
  vec3 rd = normalize(uv.x * iCameraRight + uv.y * iCameraUp + 1.0 * iCameraForward);

  float zMax = 50.;
  float z = .1;

  vec3 col = vec3(0);

  for(float i=0.;i<100.;i++){
    vec3 p = ro + rd * z;

    p = abs(p);
    p-=vec3(1,2,3);
    #ifdef allowRotate
    p.xz*=rotate(6.+T);
    p.xy*=rotate(12.+T);
    p.yz*=rotate(18.+T);
    #endif

    p = clamp(p,0.,TAU);

    // vec3 q = fract(p/4.)-.5;
    vec3 q = cos(p);
    q.yz *= rotate(10.2);

    vec3 q2 = mix(q, p, tanh(sin(T))*.5+.5);

    // float d = length(p) - 3.;
    float d = sdBoxFrame(q2, vec3(.6), .02);
    // d += fbm(p*5.)*.1;

    d = abs(d)*.4 + .01;
    // d = max(0., d);

    col += s1(vec3(3,2,1)+dot(p,q2)+T*2.)*pow(.2/d,2.);
    
    if(d<EPSILON || z>zMax) break;
    z += d;
  }

  col = tanh(col / 2e2);

  O.rgb = col;
}
