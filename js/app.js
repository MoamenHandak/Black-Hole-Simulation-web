/**
 * 3D Black Hole Raytracer & Gravity Simulator - Main Application
 */

import { BLACK_HOLE_VERTEX_SHADER, BLACK_HOLE_FRAGMENT_SHADER, SPACETIME_GRID_VERTEX_SHADER, SPACETIME_GRID_FRAGMENT_SHADER } from './shaders.js';
import { Vec3, ObjectData, GravitySimulation, SpacetimeGrid, LightGeodesicIntegrator, G, C } from './simulation.js';
import { audioEngine } from './audio.js';

class App {
    constructor() {
        this.canvas = document.getElementById('webgl-canvas');
        this.gl = null;
        
        // Render Programs
        this.raytraceProgram = null;
        this.gridProgram = null;

        // Buffers
        this.quadVao = null;
        this.gridVao = null;
        this.gridIndexCount = 0;

        // Camera State
        this.camTarget = new Vec3(0, 0, 0);
        this.camRadius = 6.34194e10;
        this.minRadius = 8.0e9;
        this.maxRadius = 1.2e12;
        this.azimuth = 0.0;
        this.elevation = Math.PI / 2.0;
        this.isDragging = false;
        this.lastMousePos = { x: 0, y: 0 };

        // Physics & Objects
        this.blackHoleMass = 4.0e30; // kg
        this.schwarzschildRadius = (2.0 * G * this.blackHoleMass) / (C * C) * 1.5e5; // Scaled for visual clarity
        
        this.diskR1 = this.schwarzschildRadius * 2.8;
        this.diskR2 = this.schwarzschildRadius * 8.5;
        this.paletteType = 0; // 0: Gold, 1: Cyan, 2: Plasma, 3: Inferno
        this.dopplerStrength = 1.0;
        this.photonGlow = 1.5;
        this.starDensity = 1.0;
        this.enableGravity = true;
        this.showSpacetimeGrid = false;
        this.showGeodesicRays = false;
        this.autoRotateCam = false;

        // Orbiting Objects (Planets/Stars)
        this.objects = [
            new ObjectData(new Vec3(3.2e10, 0, 0), 1.8e9, [0.2, 0.6, 1.0, 1.0], 5.0e26), // Blue planet
            new ObjectData(new Vec3(-4.8e10, 0, 2.0e10), 2.2e9, [1.0, 0.5, 0.2, 1.0], 8.0e26), // Orange planet
            new ObjectData(new Vec3(0, 0, -6.5e10), 3.0e9, [0.4, 0.9, 0.4, 1.0], 1.5e27), // Gas giant
        ];
        // Set initial circular orbital velocities: v = sqrt(G*M / r)
        this.initOrbits();

        this.sim = new GravitySimulation([
            new ObjectData(new Vec3(0, 0, 0), this.schwarzschildRadius, [0,0,0,1], this.blackHoleMass),
            ...this.objects
        ]);

        // Frame timing stats
        this.frameCount = 0;
        this.lastFpsTime = performance.now();
        this.fps = 60;
        this.startTime = performance.now();

        this.initWebGL();
        this.setupEventListeners();
        this.updateSpacetimeGridMesh();
        
        requestAnimationFrame((t) => this.renderLoop(t));
    }

    initOrbits() {
        for (const obj of this.objects) {
            const dist = obj.position.length();
            const orbitalSpeed = Math.sqrt((G * this.blackHoleMass) / dist) * 1.5e4;
            // Tangent direction vector
            const tangent = new Vec3(-obj.position.z, 0, obj.position.x).normalized();
            obj.velocity = tangent.mul(orbitalSpeed);
        }
    }

    initWebGL() {
        this.gl = this.canvas.getContext('webgl2', { preserveDrawingBuffer: true, antialias: true });
        if (!this.gl) {
            alert('WebGL 2.0 is not supported by your browser.');
            return;
        }

        // Compile Shader Programs
        this.raytraceProgram = this.createProgram(BLACK_HOLE_VERTEX_SHADER, BLACK_HOLE_FRAGMENT_SHADER);
        this.gridProgram = this.createProgram(SPACETIME_GRID_VERTEX_SHADER, SPACETIME_GRID_FRAGMENT_SHADER);

        // Quad VAO for Raytracing
        const quadVertices = new Float32Array([
            -1.0, -1.0,   1.0, -1.0,   1.0,  1.0,
            -1.0, -1.0,   1.0,  1.0,  -1.0,  1.0
        ]);
        this.quadVao = this.gl.createVertexArray();
        const quadVbo = this.gl.createBuffer();
        this.gl.bindVertexArray(this.quadVao);
        this.gl.bindBuffer(this.gl.ARRAY_BUFFER, quadVbo);
        this.gl.bufferData(this.gl.ARRAY_BUFFER, quadVertices, this.gl.STATIC_DRAW);
        this.gl.enableVertexAttribArray(0);
        this.gl.vertexAttribPointer(0, 2, this.gl.FLOAT, false, 0, 0);

        this.resizeCanvas();
        window.addEventListener('resize', () => this.resizeCanvas());
    }

    createProgram(vsSource, fsSource) {
        const vs = this.compileShader(this.gl.VERTEX_SHADER, vsSource);
        const fs = this.compileShader(this.gl.FRAGMENT_SHADER, fsSource);
        const program = this.gl.createProgram();
        this.gl.attachShader(program, vs);
        this.gl.attachShader(program, fs);
        this.gl.linkProgram(program);
        if (!this.gl.getProgramParameter(program, this.gl.LINK_STATUS)) {
            console.error('Program link error:', this.gl.getProgramInfoLog(program));
        }
        return program;
    }

    compileShader(type, source) {
        const shader = this.gl.createShader(type);
        this.gl.shaderSource(shader, source);
        this.gl.compileShader(shader);
        if (!this.gl.getShaderParameter(shader, this.gl.COMPILE_STATUS)) {
            console.error('Shader compile error:', this.gl.getShaderInfoLog(shader));
            this.gl.deleteShader(shader);
            return null;
        }
        return shader;
    }

    resizeCanvas() {
        const displayWidth = window.innerWidth;
        const displayHeight = window.innerHeight;
        if (this.canvas.width !== displayWidth || this.canvas.height !== displayHeight) {
            this.canvas.width = displayWidth;
            this.canvas.height = displayHeight;
            this.gl.viewport(0, 0, displayWidth, displayHeight);
        }
    }

    updateSpacetimeGridMesh() {
        const mesh = SpacetimeGrid.generateMesh(
            [new ObjectData(new Vec3(0, 0, 0), this.schwarzschildRadius, [0,0,0,1], this.blackHoleMass), ...this.objects],
            48,
            2.0e10
        );

        if (!this.gridVao) {
            this.gridVao = this.gl.createVertexArray();
        }
        this.gl.bindVertexArray(this.gridVao);

        const vbo = this.gl.createBuffer();
        this.gl.bindBuffer(this.gl.ARRAY_BUFFER, vbo);
        this.gl.bufferData(this.gl.ARRAY_BUFFER, mesh.vertices, this.gl.STATIC_DRAW);
        this.gl.enableVertexAttribArray(0);
        this.gl.vertexAttribPointer(0, 3, this.gl.FLOAT, false, 0, 0);

        const ibo = this.gl.createBuffer();
        this.gl.bindBuffer(this.gl.ELEMENT_ARRAY_BUFFER, ibo);
        this.gl.bufferData(this.gl.ELEMENT_ARRAY_BUFFER, mesh.indices, this.gl.STATIC_DRAW);

        this.gridIndexCount = mesh.indices.length;
    }

    getCameraPosition() {
        const elev = Math.max(0.01, Math.min(Math.PI - 0.01, this.elevation));
        return new Vec3(
            this.camRadius * Math.sin(elev) * Math.cos(this.azimuth),
            this.camRadius * Math.cos(elev),
            this.camRadius * Math.sin(elev) * Math.sin(this.azimuth)
        );
    }

    getCameraBasis() {
        const pos = this.getCameraPosition();
        const forward = this.camTarget.sub(pos).normalized();
        const right = forward.cross(new Vec3(0, 1, 0)).normalized();
        const up = right.cross(forward).normalized();
        return { pos, forward, right, up };
    }

    renderLoop(currentTime) {
        this.frameCount++;
        if (currentTime - this.lastFpsTime >= 1000) {
            this.fps = Math.round((this.frameCount * 1000) / (currentTime - this.lastFpsTime));
            document.getElementById('stat-fps').textContent = `${this.fps} FPS`;
            this.frameCount = 0;
            this.lastFpsTime = currentTime;
        }

        const elapsedTime = (currentTime - this.startTime) * 0.001;

        if (this.autoRotateCam) {
            this.azimuth += 0.003;
        }

        // Physics step
        if (this.enableGravity) {
            this.sim.step(true, 0.015);
            // Sync positions back to object data
            for (let i = 0; i < this.objects.length; i++) {
                this.objects[i] = this.sim.objects[i + 1];
            }
            if (this.showSpacetimeGrid) {
                this.updateSpacetimeGridMesh();
            }
        }

        // Clear Screen
        this.gl.clearColor(0.0, 0.0, 0.0, 1.0);
        this.gl.clear(this.gl.COLOR_BUFFER_BIT | this.gl.DEPTH_BUFFER_BIT);

        // Render Raytraced Black Hole
        this.renderRaytracing(elapsedTime);

        // Render Spacetime Grid Wireframe Overlay if enabled
        if (this.showSpacetimeGrid) {
            this.renderGrid();
        }

        requestAnimationFrame((t) => this.renderLoop(t));
    }

    renderRaytracing(elapsedTime) {
        const { pos, forward, right, up } = this.getCameraBasis();
        const aspect = this.canvas.width / this.canvas.height;
        const tanHalfFov = Math.tan((60.0 * Math.PI) / 360.0);

        this.gl.useProgram(this.raytraceProgram);
        this.gl.bindVertexArray(this.quadVao);

        // Set Uniforms
        const u = (name) => this.gl.getUniformLocation(this.raytraceProgram, name);
        this.gl.uniform3f(u('cam_pos'), pos.x, pos.y, pos.z);
        this.gl.uniform3f(u('cam_right'), right.x, right.y, right.z);
        this.gl.uniform3f(u('cam_up'), up.x, up.y, up.z);
        this.gl.uniform3f(u('cam_forward'), forward.x, forward.y, forward.z);
        this.gl.uniform1f(u('tan_half_fov'), tanHalfFov);
        this.gl.uniform1f(u('aspect'), aspect);
        this.gl.uniform1f(u('black_hole_rs'), this.schwarzschildRadius);
        this.gl.uniform1f(u('disk_r1'), this.diskR1);
        this.gl.uniform1f(u('disk_r2'), this.diskR2);
        this.gl.uniform1i(u('palette_type'), this.paletteType);
        this.gl.uniform1f(u('doppler_strength'), this.dopplerStrength);
        this.gl.uniform1f(u('photon_glow'), this.photonGlow);
        this.gl.uniform1f(u('star_density'), this.starDensity);
        this.gl.uniform1f(u('time'), elapsedTime);

        // Pass Orbiting Objects
        this.gl.uniform1i(u('object_count'), this.objects.length);
        for (let i = 0; i < this.objects.length; i++) {
            const obj = this.objects[i];
            const posLoc = this.gl.getUniformLocation(this.raytraceProgram, `object_pos_radius[${i}]`);
            const colLoc = this.gl.getUniformLocation(this.raytraceProgram, `object_color[${i}]`);
            this.gl.uniform4f(posLoc, obj.position.x, obj.position.y, obj.position.z, obj.radius);
            this.gl.uniform4f(colLoc, obj.color[0], obj.color[1], obj.color[2], obj.color[3]);
        }

        this.gl.drawArrays(this.gl.TRIANGLES, 0, 6);
    }

    getMVPMatrix(pos, right, up, forward, aspect) {
        const fov = (60.0 * Math.PI) / 180.0;
        const f = 1.0 / Math.tan(fov / 2.0);
        const near = 1.0e8;
        const far = 5.0e12;
        const nf = 1.0 / (near - far);

        const v0 = right.x, v1 = up.x, v2 = -forward.x;
        const v4 = right.y, v5 = up.y, v6 = -forward.y;
        const v8 = right.z, v9 = up.z, v10 = -forward.z;
        const v12 = -right.dot(pos), v13 = -up.dot(pos), v14 = forward.dot(pos);

        const p0 = f / aspect, p5 = f, p10 = (far + near) * nf, p14 = (2.0 * far * near) * nf;

        const mvp = new Float32Array(16);
        mvp[0]  = p0 * v0;
        mvp[1]  = p5 * v1;
        mvp[2]  = p10 * v2;
        mvp[3]  = -v2;

        mvp[4]  = p0 * v4;
        mvp[5]  = p5 * v5;
        mvp[6]  = p10 * v6;
        mvp[7]  = -v6;

        mvp[8]  = p0 * v8;
        mvp[9]  = p5 * v9;
        mvp[10] = p10 * v10;
        mvp[11] = -v10;

        mvp[12] = p0 * v12;
        mvp[13] = p5 * v13;
        mvp[14] = p10 * v14 + p14;
        mvp[15] = -v14;

        return mvp;
    }

    renderGrid() {
        const { pos, forward, right, up } = this.getCameraBasis();
        const aspect = this.canvas.width / this.canvas.height;
        const mvp = this.getMVPMatrix(pos, right, up, forward, aspect);

        this.gl.useProgram(this.gridProgram);
        this.gl.bindVertexArray(this.gridVao);
        this.gl.enable(this.gl.BLEND);
        this.gl.blendFunc(this.gl.SRC_ALPHA, this.gl.ONE);

        const uMvp = this.gl.getUniformLocation(this.gridProgram, 'u_mvp');
        const uCol = this.gl.getUniformLocation(this.gridProgram, 'u_color');
        
        this.gl.uniformMatrix4fv(uMvp, false, mvp);
        this.gl.uniform4f(uCol, 0.0, 0.85, 1.0, 0.65);

        this.gl.drawElements(this.gl.LINES, this.gridIndexCount, this.gl.UNSIGNED_SHORT, 0);
        this.gl.disable(this.gl.BLEND);
    }

    setupEventListeners() {
        // Orbit Controls via Mouse Drag and Touch
        const handleDragStart = (x, y) => {
            this.isDragging = true;
            this.lastMousePos = { x, y };
        };

        const handleDragMove = (x, y) => {
            if (!this.isDragging) return;
            const dx = x - this.lastMousePos.x;
            const dy = y - this.lastMousePos.y;
            this.azimuth += dx * 0.008;
            this.elevation -= dy * 0.008;
            this.elevation = Math.max(0.01, Math.min(Math.PI - 0.01, this.elevation));
            this.lastMousePos = { x, y };
        };

        const handleDragEnd = () => { this.isDragging = false; };

        this.canvas.addEventListener('mousedown', (e) => handleDragStart(e.clientX, e.clientY));
        window.addEventListener('mousemove', (e) => handleDragMove(e.clientX, e.clientY));
        window.addEventListener('mouseup', handleDragEnd);

        this.canvas.addEventListener('touchstart', (e) => {
            if (e.touches.length === 1) handleDragStart(e.touches[0].clientX, e.touches[0].clientY);
        });
        window.addEventListener('touchmove', (e) => {
            if (e.touches.length === 1) handleDragMove(e.touches[0].clientX, e.touches[0].clientY);
        });
        window.addEventListener('touchend', handleDragEnd);

        // Zoom via Mouse Wheel
        this.canvas.addEventListener('wheel', (e) => {
            e.preventDefault();
            this.camRadius = Math.max(this.minRadius, Math.min(this.maxRadius, this.camRadius + e.deltaY * 3.5e8));
            document.getElementById('stat-dist').textContent = `${(this.camRadius * 1e-9).toFixed(1)}M km`;
        }, { passive: false });

        // Sidebar Toggle
        const sidebar = document.getElementById('control-sidebar');
        const toggleBtn = document.getElementById('sidebar-toggle');
        const closeBtn = document.getElementById('sidebar-close');

        toggleBtn.addEventListener('click', () => sidebar.classList.toggle('collapsed'));
        closeBtn.addEventListener('click', () => sidebar.classList.add('collapsed'));

        // Tab Navigation
        const tabs = document.querySelectorAll('.tab-btn');
        tabs.forEach(tab => {
            tab.addEventListener('click', () => {
                tabs.forEach(t => t.classList.remove('active'));
                document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
                tab.classList.add('active');
                document.getElementById(`tab-${tab.dataset.tab}`).classList.add('active');
            });
        });

        // Sliders & Controls Bindings
        const bindSlider = (id, callback, valFormat) => {
            const el = document.getElementById(id);
            const valEl = document.getElementById(`${id}-val`);
            el.addEventListener('input', (e) => {
                const val = parseFloat(e.target.value);
                callback(val);
                if (valEl) valEl.textContent = valFormat ? valFormat(val) : val.toFixed(1);
            });
        };

        bindSlider('mass-slider', (v) => {
            this.blackHoleMass = v * 1.0e30;
            this.schwarzschildRadius = (2.0 * G * this.blackHoleMass) / (C * C) * 1.5e5;
            this.diskR1 = this.schwarzschildRadius * 2.8;
            this.diskR2 = this.schwarzschildRadius * 8.5;
            this.updateSpacetimeGridMesh();
            audioEngine.updateMassPitch(v / 10);
            document.getElementById('stat-rs').textContent = `${(this.schwarzschildRadius * 1e-6).toFixed(1)} km`;
        }, (v) => `${v.toFixed(1)} M☉`);

        bindSlider('doppler-slider', (v) => { this.dopplerStrength = v; });
        bindSlider('ring-slider', (v) => { this.photonGlow = v; });
        bindSlider('stars-slider', (v) => { this.starDensity = v; });

        // Palette Selector Buttons
        document.querySelectorAll('.palette-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.palette-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                this.paletteType = parseInt(btn.dataset.palette);
            });
        });

        // Toggles
        document.getElementById('toggle-gravity').addEventListener('change', (e) => { this.enableGravity = e.target.checked; });
        document.getElementById('toggle-grid').addEventListener('change', (e) => { this.showSpacetimeGrid = e.target.checked; });
        document.getElementById('toggle-rotate').addEventListener('change', (e) => { this.autoRotateCam = e.target.checked; });

        // Audio Mute Toggle
        const audioBtn = document.getElementById('btn-audio');
        audioBtn.addEventListener('click', () => {
            const isMuted = audioEngine.toggleMute();
            audioBtn.classList.toggle('active', !isMuted);
        });

        // Presets
        document.querySelectorAll('.preset-card').forEach(card => {
            card.addEventListener('click', () => {
                document.querySelectorAll('.preset-card').forEach(c => c.classList.remove('active'));
                card.classList.add('active');
                this.loadPreset(card.dataset.preset);
            });
        });

        // Screenshot Exporter
        document.getElementById('btn-screenshot').addEventListener('click', () => this.exportScreenshot());

        // Guide Modal
        const modal = document.getElementById('guide-modal');
        document.getElementById('btn-guide').addEventListener('click', () => modal.classList.add('active'));
        document.getElementById('modal-close').addEventListener('click', () => modal.classList.remove('active'));
    }

    loadPreset(name) {
        if (name === 'gargantua') {
            this.blackHoleMass = 6.5e30;
            this.schwarzschildRadius = (2.0 * G * this.blackHoleMass) / (C * C) * 1.5e5;
            this.diskR1 = this.schwarzschildRadius * 2.5;
            this.diskR2 = this.schwarzschildRadius * 10.0;
            this.paletteType = 0;
            this.dopplerStrength = 1.4;
            this.photonGlow = 1.8;
        } else if (name === 'm87') {
            this.blackHoleMass = 9.0e30;
            this.schwarzschildRadius = (2.0 * G * this.blackHoleMass) / (C * C) * 1.5e5;
            this.diskR1 = this.schwarzschildRadius * 3.0;
            this.diskR2 = this.schwarzschildRadius * 12.0;
            this.paletteType = 3;
            this.dopplerStrength = 0.8;
            this.photonGlow = 2.2;
        } else if (name === 'cyan') {
            this.blackHoleMass = 3.5e30;
            this.schwarzschildRadius = (2.0 * G * this.blackHoleMass) / (C * C) * 1.5e5;
            this.diskR1 = this.schwarzschildRadius * 2.8;
            this.diskR2 = this.schwarzschildRadius * 7.5;
            this.paletteType = 1;
            this.dopplerStrength = 1.1;
            this.photonGlow = 1.4;
        } else if (name === 'plasma') {
            this.blackHoleMass = 5.0e30;
            this.schwarzschildRadius = (2.0 * G * this.blackHoleMass) / (C * C) * 1.5e5;
            this.diskR1 = this.schwarzschildRadius * 2.6;
            this.diskR2 = this.schwarzschildRadius * 9.0;
            this.paletteType = 2;
            this.dopplerStrength = 1.2;
            this.photonGlow = 2.0;
        }
        this.updateSpacetimeGridMesh();
    }

    exportScreenshot() {
        const link = document.createElement('a');
        link.download = `black_hole_render_${Date.now()}.png`;
        link.href = this.canvas.toDataURL('image/png');
        link.click();
    }
}

// Instantiate on DOM load
window.addEventListener('DOMContentLoaded', () => {
    window.app = new App();
});
