/**
 * GLSL Shaders for 3D Black Hole Raytracing, Spacetime Mesh & Geodesic Ray visualization.
 */

export const BLACK_HOLE_VERTEX_SHADER = `#version 300 es
in vec2 a_pos;
out vec2 v_uv;

void main() {
    v_uv = a_pos * 0.5 + 0.5;
    gl_Position = vec4(a_pos, 0.0, 1.0);
}
`;

export const BLACK_HOLE_FRAGMENT_SHADER = `#version 300 es
precision highp float;

in vec2 v_uv;
out vec4 frag_color;

uniform vec3 cam_pos;
uniform vec3 cam_right;
uniform vec3 cam_up;
uniform vec3 cam_forward;
uniform float tan_half_fov;
uniform float aspect;
uniform float black_hole_rs;
uniform float disk_r1;
uniform float disk_r2;
uniform int palette_type; // 0: Gargantua Gold, 1: Cyber Cyan, 2: Plasma, 3: Inferno
uniform float doppler_strength;
uniform float photon_glow;
uniform float star_density;
uniform float time;
uniform int object_count;
uniform vec4 object_pos_radius[16];
uniform vec4 object_color[16];

const float EPSILON = 1e-5;
const float PI = 3.14159265358979323846;

// Pseudo-random noise helper
float hash12(vec2 p) {
    vec3 p3 = fract(vec3(p.xyx) * 0.1031);
    p3 += dot(p3, p3.yzx + 33.33);
    return fract((p3.x + p3.y) * p3.z);
}

// 2D simplex noise approximation for accretion disk turbulence
float noise(vec2 st) {
    vec2 i = floor(st);
    vec2 f = fract(st);

    float a = hash12(i);
    float b = hash12(i + vec2(1.0, 0.0));
    float c = hash12(i + vec2(0.0, 1.0));
    float d = hash12(i + vec2(1.0, 1.0));

    vec2 u = f * f * (3.0 - 2.0 * f);
    return mix(a, b, u.x) + (c - a) * u.y * (1.0 - u.x) + (d - b) * u.x * u.y;
}

float fbm(vec2 st) {
    float val = 0.0;
    float amp = 0.5;
    for (int i = 0; i < 4; i++) {
        val += amp * noise(st);
        st *= 2.05;
        amp *= 0.5;
    }
    return val;
}

// Gravitational light bending model around Schwarzschild black hole
vec3 lens_direction(vec3 dir, out float impact) {
    vec3 to_center = -cam_pos;
    float closest_t = max(dot(to_center, dir), 0.0);
    vec3 closest_point = cam_pos + dir * closest_t;
    impact = length(closest_point);
    vec3 bend_dir = -closest_point / max(impact, EPSILON);
    float forward_factor = smoothstep(0.0, 0.35, closest_t / max(length(cam_pos), EPSILON));
    float deflection = clamp(2.6 * black_hole_rs / max(impact, black_hole_rs * 0.45), 0.0, 1.45);
    return normalize(dir + bend_dir * deflection * forward_factor);
}

// Procedural nebula background gradient
vec3 background_gradient(vec3 dir) {
    float horizon = clamp(0.5 + 0.5 * dir.y, 0.0, 1.0);
    vec3 low = vec3(0.003, 0.005, 0.012);
    vec3 high = vec3(0.012, 0.02, 0.045);
    
    // Galactic plane nebula band
    float band = exp(-pow(abs(dir.y + 0.08 + 0.22 * dir.x), 2.0) * 18.0);
    vec3 nebula = vec3(0.08, 0.04, 0.12) * band * (0.8 + 0.4 * sin(dir.x * 4.0 + dir.z * 4.0));
    return mix(low, high, horizon) + nebula;
}

// Starfield generator
vec3 add_stars(vec3 dir, vec3 base_color) {
    float longitude = atan(dir.z, dir.x) / (2.0 * PI) + 0.5;
    float latitude = asin(clamp(dir.y, -1.0, 1.0)) / PI + 0.5;
    vec2 star_uv = vec2(longitude, latitude);

    vec3 color = base_color;
    for (int layer = 0; layer < 2; ++layer) {
        float scale = (layer == 0 ? 200.0 : 380.0) * star_density;
        vec2 grid = star_uv * vec2(scale * 2.0, scale);
        vec2 cell = floor(grid);
        vec2 local = fract(grid) - 0.5;
        float chance = hash12(cell + float(layer) * 19.7);
        if (chance > 0.985) {
            vec2 offset = vec2(
                hash12(cell + 1.7 + float(layer)),
                hash12(cell + 8.3 + float(layer))
            ) - 0.5;
            float glow = smoothstep(0.12, 0.0, length(local - offset * 0.55));
            vec3 tint = mix(vec3(0.7, 0.85, 1.0), vec3(1.0, 0.9, 0.75), hash12(cell + 5.2));
            color += tint * glow * (layer == 0 ? 0.9 : 0.5);
        }
    }
    return color;
}

// Background Planets (like in black_hole_demo.py)
vec3 planet_palette(vec2 uv, vec3 a, vec3 b, vec3 c) {
    float bands = 0.5 + 0.5 * sin(uv.y * 26.0 + 2.5 * sin(uv.x * 8.0));
    float storms = smoothstep(0.72, 0.95, hash12(floor(uv * 18.0) + 3.7));
    vec3 color = mix(a, b, bands);
    return mix(color, c, storms * 0.28);
}

bool sample_planet(vec3 dir, vec3 center, float angular_radius, vec3 a, vec3 b, vec3 c, out vec3 color) {
    float cosine = dot(dir, center);
    float min_cosine = cos(angular_radius);
    if (cosine <= min_cosine) return false;

    vec3 axis_a = normalize(abs(center.y) < 0.95 ? cross(vec3(0.0, 1.0, 0.0), center) : cross(vec3(1.0, 0.0, 0.0), center));
    vec3 axis_b = cross(center, axis_a);
    vec2 uv = vec2(dot(dir, axis_a), dot(dir, axis_b)) / max(sin(angular_radius), EPSILON);
    float radius2 = dot(uv, uv);
    if (radius2 > 1.0) return false;

    float rim = sqrt(max(1.0 - radius2, 0.0));
    vec3 surface = planet_palette(uv, a, b, c);
    vec3 light_dir = normalize(vec3(-0.3, 0.85, 0.4));
    vec3 normal = normalize(center * rim + axis_a * uv.x + axis_b * uv.y);
    float diffuse = 0.3 + 0.7 * max(dot(normal, light_dir), 0.0);
    color = surface * diffuse + 0.08 * pow(1.0 - rim, 4.0);
    return true;
}

vec3 sample_background(vec3 dir) {
    vec3 color = add_stars(dir, background_gradient(dir));
    vec3 planet_color = vec3(0.0);

    // Planet 1 (Gas Giant Blue)
    if (sample_planet(dir, normalize(vec3(0.82, 0.14, -0.56)), 0.16, vec3(0.15, 0.35, 0.78), vec3(0.62, 0.78, 0.96), vec3(0.95, 0.96, 1.0), planet_color)) {
        color = planet_color;
    }
    // Planet 2 (Desert Orange)
    if (sample_planet(dir, normalize(vec3(-0.45, -0.08, -0.89)), 0.12, vec3(0.72, 0.32, 0.08), vec3(0.98, 0.78, 0.26), vec3(0.55, 0.18, 0.04), planet_color)) {
        color = planet_color;
    }
    // Planet 3 (Terrestrial Green)
    if (sample_planet(dir, normalize(vec3(-0.18, 0.36, 0.91)), 0.09, vec3(0.08, 0.42, 0.24), vec3(0.32, 0.72, 0.48), vec3(0.86, 0.92, 0.74), planet_color)) {
        color = planet_color;
    }

    return color;
}

// Ray-Sphere intersection for local orbiting bodies
bool sample_local_objects(vec3 dir, out vec3 color, out float hit_t) {
    bool hit = false;
    hit_t = 1e30;
    color = vec3(0.0);
    vec3 light_dir = normalize(vec3(0.4, 1.0, 0.2));

    for (int i = 0; i < object_count; ++i) {
        vec3 center = object_pos_radius[i].xyz;
        float radius = object_pos_radius[i].w;
        vec3 oc = cam_pos - center;
        float b = dot(oc, dir);
        float c = dot(oc, oc) - radius * radius;
        float discriminant = b * b - c;
        if (discriminant < 0.0) continue;

        float t = -b - sqrt(discriminant);
        if (t > 0.0 && t < hit_t) {
            vec3 point = cam_pos + dir * t;
            vec3 normal = normalize(point - center);
            float diffuse = 0.2 + 0.8 * max(dot(normal, light_dir), 0.0);
            color = object_color[i].rgb * diffuse;
            hit_t = t;
            hit = true;
        }
    }
    return hit;
}

// Accretion Disk Sampler with relativistic Doppler shift & swirling turbulence
bool sample_disk(vec3 unbent_dir, vec3 bent_dir, out vec3 color, out float hit_t) {
    color = vec3(0.0);
    hit_t = 1e30;

    vec3 to_center = -cam_pos;
    float closest_t = max(dot(to_center, unbent_dir), 0.0);
    vec3 closest_point = cam_pos + unbent_dir * closest_t;

    bool valid_hit = false;
    vec3 point = vec3(0.0);

    // 1. Direct unbent ray intersection (front of disk)
    if (abs(unbent_dir.y) > EPSILON) {
        float t_front = -cam_pos.y / unbent_dir.y;
        if (t_front > 0.0 && t_front < closest_t) {
            vec3 p = cam_pos + unbent_dir * t_front;
            float r = length(p.xz);
            // FIX: Only register a hit if it lands inside the disk bounds
            if (r >= disk_r1 && r <= disk_r2) {
                point = p;
                hit_t = t_front;
                valid_hit = true;
            }
        }
    }

    // 2. Gravitationally bent ray intersection (halo around top/bottom)
    if (!valid_hit && abs(bent_dir.y) > EPSILON) {
        float t_back = -closest_point.y / bent_dir.y;
        if (t_back > 0.0) {
            vec3 p = closest_point + bent_dir * t_back;
            float r = length(p.xz);
            // FIX: Only register a hit if it lands inside the disk bounds
            if (r >= disk_r1 && r <= disk_r2) {
                point = p;
                hit_t = closest_t + t_back;
                valid_hit = true;
            }
        }
    }

    if (!valid_hit) return false;

    float radius = length(point.xz);
    // Note: The previous out-of-bounds check here has been removed 
    // because we already validated the radius in the steps above.

    float radial = clamp((radius - disk_r1) / max(disk_r2 - disk_r1, EPSILON), 0.0, 1.0);
    float edge = smoothstep(disk_r1, disk_r1 * 1.08, radius) * (1.0 - smoothstep(disk_r2 * 0.92, disk_r2, radius));
    
    // Dynamic spiral swirl & noise pattern
    float angle = atan(point.z, point.x);
    float swirl_speed = time * 0.8;
    float swirl_angle = angle - (swirl_speed * (disk_r1 / radius));
    float turbulent_noise = fbm(vec2(radius * 1.5e-10, swirl_angle * 3.0));
    float swirl = 0.7 + 0.3 * sin(radius * 2.8e-10 + swirl_angle * 8.0 + turbulent_noise * 4.0);

    // Accretion disk Palette Selection
    vec3 inner_col, outer_col;
    if (palette_type == 1) {
        // Cyber Cyan
        inner_col = vec3(0.9, 0.98, 1.0);
        outer_col = vec3(0.0, 0.55, 0.95);
    } else if (palette_type == 2) {
        // Plasma Violet
        inner_col = vec3(1.0, 0.8, 0.98);
        outer_col = vec3(0.6, 0.1, 0.9);
    } else if (palette_type == 3) {
        // Inferno Red
        inner_col = vec3(1.0, 0.85, 0.3);
        outer_col = vec3(0.9, 0.15, 0.05);
    } else {
        // Gargantua Gold (Default)
        inner_col = vec3(0.98, 0.82, 0.45);
        outer_col = vec3(0.72, 0.28, 0.05);
    }

    // Relativistic Doppler Beaming / Redshift
    vec3 orbital_dir = normalize(vec3(-point.z, 0.0, point.x));
    vec3 view_dir = normalize(cam_pos - point);
    float doppler_dot = dot(orbital_dir, view_dir);
    float doppler_factor = 1.0 + doppler_strength * doppler_dot;
    float brightness = pow(doppler_factor, 3.0) * mix(0.8, 1.15, swirl);

    // Doppler shift color tinting (approaching is bluer, receding is redder)
    vec3 base_color = mix(inner_col, outer_col, radial);
    if (doppler_dot > 0.0) {
        base_color = mix(base_color, vec3(0.6, 0.85, 1.0), doppler_dot * 0.4 * doppler_strength);
    } else {
        base_color = mix(base_color, vec3(0.9, 0.2, 0.1), -doppler_dot * 0.4 * doppler_strength);
    }

    color = base_color * brightness * edge * 0.85;
    return true;
}

void main() {
    float u = (2.0 * v_uv.x - 1.0) * aspect * tan_half_fov;
    float v = (1.0 - 2.0 * v_uv.y) * tan_half_fov;
    vec3 dir = normalize(u * cam_right - v * cam_up + cam_forward);
    
    float impact = 0.0;
    vec3 bent_dir = lens_direction(dir, impact);

    float shadow_radius = black_hole_rs * 2.65;
    float shadow = 1.0 - smoothstep(shadow_radius * 0.94, shadow_radius * 1.06, impact);
    float photon_ring = exp(-abs(impact - shadow_radius * 1.18) / max(black_hole_rs * 0.16, EPSILON));

    vec3 color = sample_background(bent_dir);

    vec3 object_color = vec3(0.0);
    float object_t = 1e30;
    bool object_hit = sample_local_objects(bent_dir, object_color, object_t);

    vec3 disk_color = vec3(0.0);
    float disk_t = 1e30;
    bool disk_hit = sample_disk(dir, bent_dir, disk_color, disk_t);

    if (disk_hit && (!object_hit || disk_t < object_t)) {
        color = mix(color, disk_color, smoothstep(0.0, 0.1, length(disk_color)));
        color += disk_color * 0.6; // Bloom reflection
    } else if (object_hit) {
        color = object_color;
    }

    // Photon ring glow
    vec3 ring_color;
    if (palette_type == 1) ring_color = vec3(0.4, 0.9, 1.0);
    else if (palette_type == 2) ring_color = vec3(0.95, 0.6, 1.0);
    else if (palette_type == 3) ring_color = vec3(1.0, 0.4, 0.2);
    else ring_color = vec3(1.0, 0.85, 0.45);

    color += ring_color * photon_ring * photon_glow * 0.4;
    color *= (1.0 - shadow); // Black hole event horizon shadow

    frag_color = vec4(color, 1.0);
}
`;

// Spacetime Bent Mesh Shaders
export const SPACETIME_GRID_VERTEX_SHADER = `#version 300 es
in vec3 a_position;
uniform mat4 u_mvp;

void main() {
    gl_Position = u_mvp * vec4(a_position, 1.0);
}
`;

export const SPACETIME_GRID_FRAGMENT_SHADER = `#version 300 es
precision highp float;
out vec4 frag_color;
uniform vec4 u_color;

void main() {
    frag_color = u_color;
}
`;
