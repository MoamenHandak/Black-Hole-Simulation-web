"""Interactive `pygame` + `PyOpenGL` port of `black_hole.cpp`."""

from __future__ import annotations

import argparse
from array import array
import math

import pygame
from OpenGL.GL import (
    GL_ARRAY_BUFFER,
    GL_BLEND,
    GL_COLOR_BUFFER_BIT,
    GL_COLOR_ATTACHMENT0,
    GL_DEPTH_BUFFER_BIT,
    GL_DEPTH_TEST,
    GL_FALSE,
    GL_FRAMEBUFFER,
    GL_FRAMEBUFFER_COMPLETE,
    GL_FLOAT,
    GL_FRAGMENT_SHADER,
    GL_LEQUAL,
    GL_LINES,
    GL_MODELVIEW,
    GL_ONE_MINUS_SRC_ALPHA,
    GL_PROJECTION,
    GL_QUADS,
    GL_RGBA,
    GL_SRC_ALPHA,
    GL_STATIC_DRAW,
    GL_TEXTURE_2D,
    GL_TEXTURE_MAG_FILTER,
    GL_TEXTURE_MIN_FILTER,
    GL_TRIANGLES,
    GL_TRUE,
    GL_UNSIGNED_BYTE,
    GL_VERTEX_SHADER,
    glAttachShader,
    glBegin,
    glBindBuffer,
    glBindFramebuffer,
    glBindTexture,
    glBindVertexArray,
    glBlendFunc,
    glBufferData,
    glClear,
    glClearColor,
    glCompileShader,
    glCreateProgram,
    glCreateShader,
    glColor4f,
    glDepthFunc,
    glDisable,
    glDrawArrays,
    glDrawPixels,
    glEnable,
    glEnd,
    glEnableVertexAttribArray,
    glFramebufferTexture2D,
    glGenBuffers,
    glGenFramebuffers,
    glGenTextures,
    glGenVertexArrays,
    glGetProgramInfoLog,
    glGetProgramiv,
    glGetShaderInfoLog,
    glGetShaderiv,
    glGetUniformLocation,
    glLineWidth,
    glLinkProgram,
    glLoadIdentity,
    glMatrixMode,
    glCheckFramebufferStatus,
    glShaderSource,
    glTexImage2D,
    glTexParameteri,
    glUniform1f,
    glUniform1i,
    glUniform3f,
    glUniform4f,
    glUseProgram,
    glVertexAttribPointer,
    glVertex3f,
    glViewport,
    glWindowPos2d,
    GL_COMPILE_STATUS,
    GL_LINEAR,
    GL_LINK_STATUS,
)
from OpenGL.GLU import gluLookAt, gluPerspective

from common import BlackHole, G, Vec3, clamp


class ObjectData:
    def __init__(self, position: Vec3, radius: float, color: tuple[int, int, int], mass: float) -> None:
        self.position = position
        self.radius = float(radius)
        self.color = color
        self.mass = float(mass)
        self.velocity = Vec3()


class GravitySimulation:
    def __init__(self, objects: list[ObjectData]) -> None:
        self.objects = objects

    def step(self, enable_gravity: bool) -> None:
        if not enable_gravity:
            return False

        accelerations = [Vec3() for _ in self.objects]
        anchor_index = max(range(len(self.objects)), key=lambda index: self.objects[index].mass)
        for index, obj in enumerate(self.objects):
            for other_index, other in enumerate(self.objects):
                if index == other_index:
                    continue

                offset = other.position - obj.position
                distance = max(offset.length(), 1.0)
                direction = offset / distance
                force = (G * obj.mass * other.mass) / (distance * distance)
                accelerations[index] = accelerations[index] + direction * (force / obj.mass)

        for index, (obj, acceleration) in enumerate(zip(self.objects, accelerations)):
            if index == anchor_index:
                obj.velocity = Vec3()
                continue
            obj.velocity = obj.velocity + acceleration
            obj.position = obj.position + obj.velocity
        return True


class OrbitCamera:
    def __init__(self) -> None:
        self.target = Vec3()
        self.radius = 6.34194e10
        self.min_radius = 1.0e10
        self.max_radius = 1.0e12
        self.azimuth = 0.0
        self.elevation = math.pi / 2.0
        self.orbit_speed = 0.01
        self.zoom_speed = 2.5e10
        self.dragging = False
        self.moving = False
        self.last_mouse = (0, 0)

    def position(self) -> Vec3:
        elevation = clamp(self.elevation, 0.01, math.pi - 0.01)
        return Vec3(
            self.radius * math.sin(elevation) * math.cos(self.azimuth),
            self.radius * math.cos(elevation),
            self.radius * math.sin(elevation) * math.sin(self.azimuth),
        )

    def handle_event(self, event: pygame.event.Event) -> bool:
        moved = False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.dragging = True
            self.moving = True
            self.last_mouse = event.pos
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.dragging = False
            self.moving = False
        elif event.type == pygame.MOUSEMOTION and self.dragging:
            dx = event.pos[0] - self.last_mouse[0]
            dy = event.pos[1] - self.last_mouse[1]
            self.azimuth += dx * self.orbit_speed
            self.elevation -= dy * self.orbit_speed
            self.elevation = clamp(self.elevation, 0.01, math.pi - 0.01)
            self.last_mouse = event.pos
            moved = True
        elif event.type == pygame.MOUSEWHEEL:
            self.radius = clamp(self.radius - event.y * self.zoom_speed, self.min_radius, self.max_radius)
            self.moving = True
            moved = True
        return moved

    def basis(self) -> tuple[Vec3, Vec3, Vec3]:
        position = self.position()
        forward = (self.target - position).normalized()
        right = forward.cross(Vec3(0.0, 1.0, 0.0)).normalized()
        up = right.cross(forward).normalized()
        return forward, right, up


def generate_grid(objects: list[ObjectData], grid_size: int = 25, spacing: float = 1.0e10) -> list[list[tuple[float, float, float]]]:
    rows: list[list[tuple[float, float, float]]] = []

    for z in range(grid_size + 1):
        row: list[tuple[float, float, float]] = []
        for x in range(grid_size + 1):
            world_x = (x - grid_size / 2) * spacing
            world_z = (z - grid_size / 2) * spacing
            height = 0.0

            for obj in objects:
                radius = 2.0 * G * obj.mass / (299_792_458.0**2)
                dx = world_x - obj.position.x
                dz = world_z - obj.position.z
                distance = math.sqrt(dx * dx + dz * dz)
                if distance > radius:
                    height += 2.0 * math.sqrt(radius * (distance - radius)) - 3.0e10
                else:
                    height += 2.0 * radius - 3.0e10

            point = (world_x, height, world_z)
            row.append(point)

        rows.append(row)

    columns = [[rows[z][x] for z in range(grid_size + 1)] for x in range(grid_size + 1)]
    return rows + columns


PRESENT_VERTEX_SHADER = """
#version 330 core
layout (location = 0) in vec2 a_pos;
out vec2 v_uv;

void main() {
    v_uv = a_pos * 0.5 + 0.5;
    gl_Position = vec4(a_pos, 0.0, 1.0);
}
"""


PRESENT_FRAGMENT_SHADER = """
#version 330 core
in vec2 v_uv;
out vec4 frag_color;

uniform sampler2D screen_texture;

void main() {
    vec3 color = texture(screen_texture, v_uv).rgb;
    frag_color = vec4(color, 1.0);
}
"""


FULLSCREEN_VERTEX_SHADER = """
#version 330 core
layout (location = 0) in vec2 a_pos;
out vec2 v_uv;

void main() {
    v_uv = a_pos * 0.5 + 0.5;
    gl_Position = vec4(a_pos, 0.0, 1.0);
}
"""


FULLSCREEN_FRAGMENT_SHADER = """
#version 330 core
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
uniform int object_count;
uniform vec4 object_pos_radius[16];
uniform vec4 object_color[16];

const float EPSILON = 1e-5;
const float PI = 3.141592653589793;

float hash12(vec2 p) {
    vec3 p3 = fract(vec3(p.xyx) * 0.1031);
    p3 += dot(p3, p3.yzx + 33.33);
    return fract((p3.x + p3.y) * p3.z);
}

vec3 lens_direction(vec3 dir, out float impact) {
    vec3 to_center = -cam_pos;
    float closest_t = max(dot(to_center, dir), 0.0);
    vec3 closest_point = cam_pos + dir * closest_t;
    impact = length(closest_point);
    vec3 bend_dir = -closest_point / max(impact, EPSILON);
    float forward_factor = smoothstep(0.0, 0.35, closest_t / max(length(cam_pos), EPSILON));
    float deflection = clamp(2.4 * black_hole_rs / max(impact, black_hole_rs * 0.45), 0.0, 1.35);
    return normalize(dir + bend_dir * deflection * forward_factor);
}

vec3 background_gradient(vec3 dir) {
    float horizon = clamp(0.5 + 0.5 * dir.y, 0.0, 1.0);
    vec3 low = vec3(0.005, 0.006, 0.012);
    vec3 high = vec3(0.018, 0.025, 0.045);
    float band = exp(-pow(abs(dir.y + 0.08 + 0.22 * dir.x), 2.0) * 24.0);
    vec3 nebula = vec3(0.06, 0.035, 0.09) * band;
    return mix(low, high, horizon) + nebula;
}

vec3 add_stars(vec3 dir, vec3 base_color) {
    float longitude = atan(dir.z, dir.x) / (2.0 * PI) + 0.5;
    float latitude = asin(clamp(dir.y, -1.0, 1.0)) / PI + 0.5;
    vec2 star_uv = vec2(longitude, latitude);

    vec3 color = base_color;
    for (int layer = 0; layer < 2; ++layer) {
        float scale = layer == 0 ? 180.0 : 320.0;
        vec2 grid = star_uv * vec2(scale * 2.0, scale);
        vec2 cell = floor(grid);
        vec2 local = fract(grid) - 0.5;
        float chance = hash12(cell + float(layer) * 19.7);
        if (chance > 0.992) {
            vec2 offset = vec2(
                hash12(cell + 1.7 + float(layer)),
                hash12(cell + 8.3 + float(layer))
            ) - 0.5;
            float glow = smoothstep(0.11, 0.0, length(local - offset * 0.55));
            vec3 tint = mix(vec3(0.7, 0.8, 1.0), vec3(1.0, 0.92, 0.8), hash12(cell + 5.2));
            color += tint * glow * (layer == 0 ? 0.85 : 0.45);
        }
    }

    return color;
}

vec3 planet_palette(vec2 uv, vec3 a, vec3 b, vec3 c) {
    float bands = 0.5 + 0.5 * sin(uv.y * 26.0 + 2.5 * sin(uv.x * 8.0));
    float storms = smoothstep(0.72, 0.95, hash12(floor(uv * 18.0) + 3.7));
    vec3 color = mix(a, b, bands);
    return mix(color, c, storms * 0.28);
}

bool sample_planet(vec3 dir, vec3 center, float angular_radius, vec3 a, vec3 b, vec3 c, out vec3 color) {
    float cosine = dot(dir, center);
    float min_cosine = cos(angular_radius);
    if (cosine <= min_cosine) {
        return false;
    }

    vec3 axis_a = normalize(abs(center.y) < 0.95 ? cross(vec3(0.0, 1.0, 0.0), center) : cross(vec3(1.0, 0.0, 0.0), center));
    vec3 axis_b = cross(center, axis_a);
    vec2 uv = vec2(dot(dir, axis_a), dot(dir, axis_b)) / max(sin(angular_radius), EPSILON);
    float radius2 = dot(uv, uv);
    if (radius2 > 1.0) {
        return false;
    }

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

    if (sample_planet(
        dir,
        normalize(vec3(0.82, 0.14, -0.56)),
        0.18,
        vec3(0.15, 0.35, 0.78),
        vec3(0.62, 0.78, 0.96),
        vec3(0.95, 0.96, 1.0),
        planet_color
    )) {
        color = planet_color;
    }

    if (sample_planet(
        dir,
        normalize(vec3(-0.45, -0.08, -0.89)),
        0.14,
        vec3(0.72, 0.32, 0.08),
        vec3(0.98, 0.78, 0.26),
        vec3(0.55, 0.18, 0.04),
        planet_color
    )) {
        color = planet_color;
    }

    if (sample_planet(
        dir,
        normalize(vec3(-0.18, 0.36, 0.91)),
        0.11,
        vec3(0.08, 0.42, 0.24),
        vec3(0.32, 0.72, 0.48),
        vec3(0.86, 0.92, 0.74),
        planet_color
    )) {
        color = planet_color;
    }

    return color;
}

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
        if (discriminant < 0.0) {
            continue;
        }

        float t = -b - sqrt(discriminant);
        if (t > 0.0 && t < hit_t) {
            vec3 point = cam_pos + dir * t;
            vec3 normal = normalize(point - center);
            float diffuse = 0.18 + 0.82 * max(dot(normal, light_dir), 0.0);
            color = object_color[i].rgb * diffuse;
            hit_t = t;
            hit = true;
        }
    }

    return hit;
}

bool sample_disk(vec3 unbent_dir, vec3 bent_dir, out vec3 color, out float hit_t) {
    color = vec3(0.0);
    hit_t = 1e30;

    // Find the point where the ray is closest to the black hole
    vec3 to_center = -cam_pos;
    float closest_t = max(dot(to_center, unbent_dir), 0.0);
    vec3 closest_point = cam_pos + unbent_dir * closest_t;

    bool valid_hit = false;
    vec3 point = vec3(0.0);

    // 1. Check the front of the disk (using the unbent ray)
    if (abs(unbent_dir.y) > EPSILON) {
        float t_front = -cam_pos.y / unbent_dir.y;
        if (t_front > 0.0 && t_front < closest_t) {
            point = cam_pos + unbent_dir * t_front;
            hit_t = t_front;
            valid_hit = true;
        }
    }

    // 2. Check the warped halos (using the bent ray from the closest point)
    if (!valid_hit && abs(bent_dir.y) > EPSILON) {
        float t_back = -closest_point.y / bent_dir.y;
        if (t_back > 0.0) {
            point = closest_point + bent_dir * t_back;
            hit_t = closest_t + t_back;
            valid_hit = true;
        }
    }

    if (!valid_hit) {
        return false;
    }

    float radius = length(point.xz);
    if (radius < disk_r1 || radius > disk_r2) {
        return false;
    }

    float radial = clamp((radius - disk_r1) / max(disk_r2 - disk_r1, EPSILON), 0.0, 1.0);
    float edge = smoothstep(disk_r1, disk_r1 * 1.08, radius) * (1.0 - smoothstep(disk_r2 * 0.92, disk_r2, radius));
    float swirl = 0.75 + 0.25 * sin(radius * 2.8e-10 + atan(point.z, point.x) * 7.0);
    vec3 inner = vec3(0.95, 0.76, 0.34);
    vec3 outer = vec3(0.68, 0.24, 0.05);
    vec3 orbital = normalize(vec3(-point.z, 0.0, point.x));
    float doppler = 0.5 + 0.5 * dot(orbital, normalize(cam_pos - point));
    float brightness = mix(0.78, 1.04, doppler) * mix(0.84, 1.0, swirl);
    color = mix(inner, outer, radial) * brightness * edge * 0.72;
    return true;
}

void main() {
    float u = (2.0 * v_uv.x - 1.0) * aspect * tan_half_fov;
    float v = (1.0 - 2.0 * v_uv.y) * tan_half_fov;
    vec3 dir = normalize(u * cam_right - v * cam_up + cam_forward);
    float impact = 0.0;
    vec3 bent_dir = lens_direction(dir, impact);

    float shadow_radius = black_hole_rs * 2.7;
    float shadow = 1.0 - smoothstep(shadow_radius * 0.92, shadow_radius * 1.08, impact);
    float photon_ring = exp(-abs(impact - shadow_radius * 1.28) / max(black_hole_rs * 0.18, EPSILON));

    vec3 color = sample_background(bent_dir);

    vec3 object_color = vec3(0.0);
    float object_t = 1e30;
    bool object_hit = sample_local_objects(bent_dir, object_color, object_t);

    vec3 disk_color = vec3(0.0);
    float disk_t = 1e30;
    bool disk_hit = sample_disk(dir, bent_dir, disk_color, disk_t);

    if (disk_hit && (!object_hit || disk_t < object_t)) {
        color = disk_color;
    } else if (object_hit) {
        color = object_color;
    }

    color += vec3(1.0, 0.82, 0.42) * photon_ring * 0.25;
    color *= 1.0 - shadow;
    frag_color = vec4(color, 1.0);
}
"""


class GpuRaytracer:
    def __init__(self, window_width: int, window_height: int) -> None:
        self.program = self._create_program(FULLSCREEN_VERTEX_SHADER, FULLSCREEN_FRAGMENT_SHADER)
        self.present_program = self._create_program(PRESENT_VERTEX_SHADER, PRESENT_FRAGMENT_SHADER)
        quad_vertices = array(
            "f",
            [
            -1.0, -1.0,
            1.0, -1.0,
            1.0, 1.0,
            -1.0, -1.0,
            1.0, 1.0,
            -1.0, 1.0,
            ],
        )
        self.vao = glGenVertexArrays(1)
        self.vbo = glGenBuffers(1)
        glBindVertexArray(self.vao)
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        glBufferData(GL_ARRAY_BUFFER, len(quad_vertices) * 4, quad_vertices.tobytes(), GL_STATIC_DRAW)
        glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 0, None)
        glEnableVertexAttribArray(0)
        glBindBuffer(GL_ARRAY_BUFFER, 0)
        glBindVertexArray(0)

        self.uniform_locations = {
            "cam_pos": glGetUniformLocation(self.program, "cam_pos"),
            "cam_right": glGetUniformLocation(self.program, "cam_right"),
            "cam_up": glGetUniformLocation(self.program, "cam_up"),
            "cam_forward": glGetUniformLocation(self.program, "cam_forward"),
            "tan_half_fov": glGetUniformLocation(self.program, "tan_half_fov"),
            "aspect": glGetUniformLocation(self.program, "aspect"),
            "black_hole_rs": glGetUniformLocation(self.program, "black_hole_rs"),
            "disk_r1": glGetUniformLocation(self.program, "disk_r1"),
            "disk_r2": glGetUniformLocation(self.program, "disk_r2"),
            "object_count": glGetUniformLocation(self.program, "object_count"),
        }
        self.object_pos_locations = [
            glGetUniformLocation(self.program, f"object_pos_radius[{index}]")
            for index in range(16)
        ]
        self.object_color_locations = [
            glGetUniformLocation(self.program, f"object_color[{index}]")
            for index in range(16)
        ]
        self.present_texture_location = glGetUniformLocation(self.present_program, "screen_texture")

        self.render_width = max(640, window_width)
        self.render_height = max(360, window_height)
        self.framebuffer = glGenFramebuffers(1)
        self.color_texture = glGenTextures(1)
        self._resize_render_target(self.render_width, self.render_height)

    def _create_program(self, vertex_source: str, fragment_source: str) -> int:
        vertex_shader = glCreateShader(GL_VERTEX_SHADER)
        glShaderSource(vertex_shader, vertex_source)
        glCompileShader(vertex_shader)
        if glGetShaderiv(vertex_shader, GL_COMPILE_STATUS) != GL_TRUE:
            raise RuntimeError(glGetShaderInfoLog(vertex_shader).decode("utf-8"))

        fragment_shader = glCreateShader(GL_FRAGMENT_SHADER)
        glShaderSource(fragment_shader, fragment_source)
        glCompileShader(fragment_shader)
        if glGetShaderiv(fragment_shader, GL_COMPILE_STATUS) != GL_TRUE:
            raise RuntimeError(glGetShaderInfoLog(fragment_shader).decode("utf-8"))

        program = glCreateProgram()
        glAttachShader(program, vertex_shader)
        glAttachShader(program, fragment_shader)
        glLinkProgram(program)
        if glGetProgramiv(program, GL_LINK_STATUS) != GL_TRUE:
            raise RuntimeError(glGetProgramInfoLog(program).decode("utf-8"))
        return program

    def _resize_render_target(self, width: int, height: int) -> None:
        self.render_width = width
        self.render_height = height
        glBindTexture(GL_TEXTURE_2D, self.color_texture)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, width, height, 0, GL_RGBA, GL_UNSIGNED_BYTE, None)

        glBindFramebuffer(GL_FRAMEBUFFER, self.framebuffer)
        glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, self.color_texture, 0)
        status = glCheckFramebufferStatus(GL_FRAMEBUFFER)
        glBindFramebuffer(GL_FRAMEBUFFER, 0)
        if status != GL_FRAMEBUFFER_COMPLETE:
            raise RuntimeError("Failed to create raytracing framebuffer.")

    def draw(self, camera: OrbitCamera, black_hole: BlackHole, objects: list[ObjectData], width: int, height: int) -> None:
        forward, right, up = camera.basis()
        position = camera.position()

        scale = 0.72 if camera.moving else 1.0
        target_width = max(640, int(width * scale))
        target_height = max(360, int(height * scale))
        if (target_width, target_height) != (self.render_width, self.render_height):
            self._resize_render_target(target_width, target_height)

        glBindFramebuffer(GL_FRAMEBUFFER, self.framebuffer)
        glViewport(0, 0, self.render_width, self.render_height)
        glDisable(GL_BLEND)
        glDisable(GL_DEPTH_TEST)
        glClear(GL_COLOR_BUFFER_BIT)
        glUseProgram(self.program)
        glUniform3f(self.uniform_locations["cam_pos"], position.x, position.y, position.z)
        glUniform3f(self.uniform_locations["cam_right"], right.x, right.y, right.z)
        glUniform3f(self.uniform_locations["cam_up"], up.x, up.y, up.z)
        glUniform3f(self.uniform_locations["cam_forward"], forward.x, forward.y, forward.z)
        glUniform1f(self.uniform_locations["tan_half_fov"], math.tan(math.radians(60.0) * 0.5))
        glUniform1f(self.uniform_locations["aspect"], self.render_width / self.render_height)
        glUniform1f(self.uniform_locations["black_hole_rs"], black_hole.schwarzschild_radius)
        glUniform1f(self.uniform_locations["disk_r1"], black_hole.schwarzschild_radius * 5.0)
        glUniform1f(self.uniform_locations["disk_r2"], black_hole.schwarzschild_radius * 11.0)

        visible_objects = [obj for obj in objects if obj.mass < black_hole.mass * 0.99][:16]
        glUniform1i(self.uniform_locations["object_count"], len(visible_objects))

        for index in range(16):
            if index < len(visible_objects):
                obj = visible_objects[index]
                glUniform4f(self.object_pos_locations[index], obj.position.x, obj.position.y, obj.position.z, obj.radius)
                red, green, blue = obj.color
                glUniform4f(self.object_color_locations[index], red / 255.0, green / 255.0, blue / 255.0, 1.0)
            else:
                glUniform4f(self.object_pos_locations[index], 0.0, 0.0, 0.0, 0.0)
                glUniform4f(self.object_color_locations[index], 0.0, 0.0, 0.0, 0.0)

        glBindVertexArray(self.vao)
        glDrawArrays(GL_TRIANGLES, 0, 6)
        glBindVertexArray(0)
        glUseProgram(0)
        glBindFramebuffer(GL_FRAMEBUFFER, 0)
        glViewport(0, 0, width, height)
        glDisable(GL_BLEND)

        glUseProgram(self.present_program)
        glBindTexture(GL_TEXTURE_2D, self.color_texture)
        glUniform1i(self.present_texture_location, 0)
        glBindVertexArray(self.vao)
        glDrawArrays(GL_TRIANGLES, 0, 6)
        glBindVertexArray(0)
        glUseProgram(0)
        glEnable(GL_BLEND)
        glEnable(GL_DEPTH_TEST)


class BlackHoleApp:
    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self.black_hole = BlackHole(Vec3(), 8.54e36)
        self.objects = build_default_objects(self.black_hole)
        self.simulation = GravitySimulation(self.objects)
        self.camera = OrbitCamera()
        self.gravity_enabled = False
        self.running = True
        self.grid_lines = generate_grid(self.objects)
        self.grid_dirty = False
        self.show_grid = True

        pygame.init()
        pygame.display.set_mode((width, height), pygame.DOUBLEBUF | pygame.OPENGL)
        pygame.display.set_caption("Black Hole Python Port")
        glViewport(0, 0, width, height)
        glClearColor(0.0, 0.0, 0.0, 1.0)
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glDepthFunc(GL_LEQUAL)
        self.raytracer = GpuRaytracer(width, height)
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("consolas", 18)
        self.fps_label = "FPS: 0.0"
        self.fps_pixels = b""
        self.fps_size = (0, 0)
        self.last_fps_refresh = 0
        self._refresh_fps_overlay(force=True)

    def handle_events(self) -> None:
        self.camera.moving = False
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                continue

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_g:
                    self.gravity_enabled = not self.gravity_enabled
                elif event.key == pygame.K_f:  # <-- Add this block to toggle the grid
                    self.show_grid = not self.show_grid
            
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
                self.gravity_enabled = True

            if event.type == pygame.MOUSEBUTTONUP and event.button == 3:
                self.gravity_enabled = False

            moved = self.camera.handle_event(event)
            self.camera.moving = self.camera.moving or moved or self.camera.dragging

    def draw_grid(self) -> None:
        glColor4f(0.4, 0.7, 1.0, 0.65)
        glLineWidth(1.0)
        for line in self.grid_lines:
            if len(line) < 2:
                continue
            glBegin(GL_LINES)
            for start, end in zip(line, line[1:]):
                glVertex3f(*start)
                glVertex3f(*end)
            glEnd()

    def draw_scene(self) -> None:
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        self.raytracer.draw(self.camera, self.black_hole, self.objects, self.width, self.height)

        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(60.0, self.width / self.height, 1.0e9, 1.0e14)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()

        camera_position = self.camera.position()
        gluLookAt(
            camera_position.x,
            camera_position.y,
            camera_position.z,
            self.camera.target.x,
            self.camera.target.y,
            self.camera.target.z,
            0.0,
            1.0,
            0.0,
        )
        if self.show_grid:  # <-- Add this condition
            self.draw_grid()
        self.draw_fps_overlay()
        pygame.display.flip()

    def draw_fps_overlay(self) -> None:
        glWindowPos2d(12, self.height - 28)
        glDrawPixels(self.fps_size[0], self.fps_size[1], GL_RGBA, GL_UNSIGNED_BYTE, self.fps_pixels)

    def _refresh_fps_overlay(self, force: bool = False) -> None:
        now = pygame.time.get_ticks()
        if not force and now - self.last_fps_refresh < 150:
            return
        self.last_fps_refresh = now
        self.fps_label = f"FPS: {self.clock.get_fps():5.1f}"
        fps_surface = self.font.render(self.fps_label, True, (240, 240, 240), (0, 0, 0))
        self.fps_size = fps_surface.get_width(), fps_surface.get_height()
        self.fps_pixels = pygame.image.tostring(fps_surface, "RGBA", True)

    def run(self) -> None:
        while self.running:
            self.handle_events()
            if self.simulation.step(self.gravity_enabled):
                self.grid_dirty = True
            if self.grid_dirty:
                self.grid_lines = generate_grid(self.objects)
                self.grid_dirty = False
            self.draw_scene()
            self.clock.tick()
            self._refresh_fps_overlay()

        pygame.quit()


def build_default_objects(black_hole: BlackHole) -> list[ObjectData]:
    return [
        ObjectData(Vec3(4.0e11, 0.0, 0.0), 4.0e10, (255, 255, 0), 1.98892e30),
        ObjectData(Vec3(0.0, 0.0, 4.0e11), 4.0e10, (255, 0, 0), 1.98892e30),
        ObjectData(Vec3(), black_hole.schwarzschild_radius, (0, 0, 0), black_hole.mass),
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the interactive pygame/PyOpenGL black hole demo.")
    parser.add_argument("--width", type=int, default=960)
    parser.add_argument("--height", type=int, default=540)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if min(args.width, args.height) <= 0:
        raise ValueError("All dimensions must be positive integers.")

    print("Controls: left-drag to orbit, mouse wheel to zoom, right mouse hold or G to enable gravity.")
    app = BlackHoleApp(args.width, args.height)
    app.run()


if __name__ == "__main__":
    main()
