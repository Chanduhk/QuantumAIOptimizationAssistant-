import { useEffect, useRef, type MutableRefObject } from "react";

const vertexSource = `
attribute vec2 position;
void main() { gl_Position = vec4(position, 0.0, 1.0); }
`;

const fragmentSource = `
precision mediump float;
uniform vec2 resolution;
uniform float time;
uniform float motion;
uniform vec3 view;
float hash(vec3 p) { p = fract(p * 0.3183099 + vec3(.1)); p *= 17.0; return fract(p.x * p.y * p.z * (p.x + p.y + p.z)); }
void main() {
  vec2 uv = (gl_FragCoord.xy - 0.5 * resolution) / min(resolution.x, resolution.y);
  float t = time * motion * 0.45;
  // Deep midnight navy and space-black foundation
  vec3 color = vec3(0.012, 0.016, 0.034);
  float haze = exp(-length(uv) * 2.5);
  color += vec3(0.025, 0.045, 0.11) * haze * 0.45;

  // Subtle realistic stardust and twinkling pearl stars
  float star = step(.9985, hash(vec3(floor(gl_FragCoord.xy * .18), 2.0)));
  color += star * (0.35 + 0.2 * sin(t * 0.8 + gl_FragCoord.x * 0.05)) * vec3(0.88, 0.92, 0.98);

  vec3 ro = vec3(0.0, 0.0, 2.8);
  vec3 rd = normalize(vec3(uv / max(view.z, .7), -1.7));
  float b = dot(ro, rd);
  float c = dot(ro, ro) - .88;
  float disc = b*b - c;
  if (disc > 0.0) {
    float d = -b - sqrt(disc);
    vec3 p = ro + rd * d;
    vec3 n = normalize(p);
    float longitude = atan(n.y, n.x) + view.y;
    float latitude = asin(clamp(n.z, -1.0, 1.0)) + view.x;
    float flow1 = sin(longitude * 10.0 + latitude * 6.0 + t * 0.6 + sin(latitude * 7.0 - t * 0.5) * .6);
    float flow2 = sin(longitude * 16.0 - latitude * 8.0 - t * 0.4 + cos(longitude * 4.0 + t * 0.5) * .5);
    float filaments = smoothstep(.74, .98, max(flow1, flow2));
    float fine = smoothstep(.85, .99, sin(longitude * 28.0 + latitude * 18.0 + t * .3));
    float fresnel = pow(1.0 - max(dot(n, normalize(ro - p)), 0.0), 2.4);
    float grain = hash(floor(n * 32.0 + t * .04));

    // Muted cosmic indigo and celestial midnight tones
    vec3 base = mix(vec3(0.035, 0.065, 0.15), vec3(0.08, 0.06, 0.18), .5 + .5 * sin(latitude * 3.0 + longitude * 2.0 - t * .15));
    color = mix(color, base, .78);
    // Soft celestial blue and soft cosmic indigo starlight dust (no neon!)
    color += filaments * vec3(0.35, 0.52, 0.78) * 0.45;
    color += fine * vec3(0.42, 0.38, 0.65) * 0.28;
    color += fresnel * vec3(0.32, 0.48, 0.72) * 0.42;
    color += grain * .018;

    float core = exp(-dot(uv, uv) * 42.0);
    color += core * vec3(0.45, 0.56, 0.78) * 0.25;
  }
  float radius = length(uv);
  float orbit = abs(radius - (1.06 + .025 * sin(atan(uv.y, uv.x) * 3.0 + t * .3)));
  float orbit2 = abs(radius - (1.18 + .018 * sin(atan(uv.y, uv.x) * 2.0 - t * .2)));
  float orbitGlow = exp(-orbit * 46.0) * .45 + exp(-orbit2 * 40.0) * .25;
  // Faint celestial dust ring
  color += orbitGlow * vec3(0.24, 0.38, 0.60) * 0.22;
  gl_FragColor = vec4(color, 1.0);
}
`;

function compile(gl: WebGLRenderingContext, type: number, source: string): WebGLShader {
  const shader = gl.createShader(type);
  if (!shader) throw new Error("WebGL shader allocation failed.");
  gl.shaderSource(shader, source);
  gl.compileShader(shader);
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    const message = gl.getShaderInfoLog(shader) ?? "WebGL shader compilation failed.";
    gl.deleteShader(shader);
    throw new Error(message);
  }
  return shader;
}

export interface NeuralCoreView {
  rotationX: number;
  rotationY: number;
  zoom: number;
}

function readView(ref: MutableRefObject<NeuralCoreView>): NeuralCoreView {
  return ref.current;
}

export function NeuralCoreCanvas({ active, onUnavailable, viewRef }: { active: boolean; onUnavailable: () => void; viewRef: MutableRefObject<NeuralCoreView> }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const activeRef = useRef(active);

  useEffect(() => {
    activeRef.current = active;
  }, [active]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    let gl: WebGLRenderingContext | null = null;
    let animation = 0;
    let program: WebGLProgram | null = null;
    let buffer: WebGLBuffer | null = null;
    const reducedMotion = typeof window.matchMedia === "function"
      ? window.matchMedia("(prefers-reduced-motion: reduce)")
      : ({ matches: false, addEventListener: () => undefined, removeEventListener: () => undefined } as unknown as MediaQueryList);
    const setFallback = () => onUnavailable();

    try {
      gl = canvas.getContext("webgl", { alpha: false, antialias: false, powerPreference: "low-power" });
      if (!gl) throw new Error("WebGL is unavailable.");
      program = gl.createProgram();
      if (!program) throw new Error("WebGL program allocation failed.");
      const vertex = compile(gl, gl.VERTEX_SHADER, vertexSource);
      const fragment = compile(gl, gl.FRAGMENT_SHADER, fragmentSource);
      gl.attachShader(program, vertex);
      gl.attachShader(program, fragment);
      gl.linkProgram(program);
      gl.deleteShader(vertex);
      gl.deleteShader(fragment);
      if (!gl.getProgramParameter(program, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(program) ?? "WebGL program linking failed.");
      buffer = gl.createBuffer();
      if (!buffer) throw new Error("WebGL geometry allocation failed.");
      gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
      gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, -1, 1, 1, -1, 1, 1]), gl.STATIC_DRAW);
      gl.useProgram(program);
      const position = gl.getAttribLocation(program, "position");
      gl.enableVertexAttribArray(position);
      gl.vertexAttribPointer(position, 2, gl.FLOAT, false, 0, 0);
      const resolution = gl.getUniformLocation(program, "resolution");
      const time = gl.getUniformLocation(program, "time");
      const motion = gl.getUniformLocation(program, "motion");
      const view = gl.getUniformLocation(program, "view");

      const resize = () => {
        if (!gl) return;
        const rect = canvas.getBoundingClientRect();
        const dpr = Math.min(window.devicePixelRatio || 1, window.innerWidth < 700 ? 1 : 1.35);
        const width = Math.max(1, Math.round(rect.width * dpr));
        const height = Math.max(1, Math.round(rect.height * dpr));
        if (canvas.width !== width || canvas.height !== height) {
          canvas.width = width;
          canvas.height = height;
          gl.viewport(0, 0, width, height);
        }
      };
      const draw = (now: number) => {
        if (!gl || !program) return;
        resize();
        gl.uniform2f(resolution, canvas.width, canvas.height);
        gl.uniform1f(time, reducedMotion.matches ? 0.0 : now * 0.001);
        gl.uniform1f(motion, reducedMotion.matches ? 0.0 : activeRef.current ? 1.0 : 0.48);
        const currentView = readView(viewRef);
        gl.uniform3f(view, currentView.rotationX, currentView.rotationY, currentView.zoom);
        gl.drawArrays(gl.TRIANGLES, 0, 6);
        if (!reducedMotion.matches) animation = window.requestAnimationFrame(draw);
      };
      const restart = () => {
        window.cancelAnimationFrame(animation);
        animation = window.requestAnimationFrame(draw);
      };
      const observer = new ResizeObserver(restart);
      observer.observe(canvas);
      reducedMotion.addEventListener("change", restart);
      canvas.addEventListener("webglcontextlost", setFallback, { once: true });
      restart();
      return () => {
        observer.disconnect();
        reducedMotion.removeEventListener("change", restart);
        canvas.removeEventListener("webglcontextlost", setFallback);
        window.cancelAnimationFrame(animation);
        if (gl && buffer) gl.deleteBuffer(buffer);
        if (gl && program) gl.deleteProgram(program);
        if (gl) gl.getExtension("WEBGL_lose_context")?.loseContext();
      };
    } catch {
      setFallback();
    }
    return () => {
      window.cancelAnimationFrame(animation);
      if (gl && buffer) gl.deleteBuffer(buffer);
      if (gl && program) gl.deleteProgram(program);
    };
  }, [onUnavailable, viewRef]);

  return <canvas ref={canvasRef} className="absolute inset-0 h-full w-full" aria-hidden="true" />;
}
