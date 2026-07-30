/**
 * Physics, Math and Simulation Engine for 3D Black Hole Web Application.
 */

export const G = 6.67430e-11;
export const C = 299792458.0;

export class Vec3 {
    constructor(x = 0.0, y = 0.0, z = 0.0) {
        this.x = Number(x);
        this.y = Number(y);
        this.z = Number(z);
    }

    add(v) { return new Vec3(this.x + v.x, this.y + v.y, this.z + v.z); }
    sub(v) { return new Vec3(this.x - v.x, this.y - v.y, this.z - v.z); }
    mul(s) { return new Vec3(this.x * s, this.y * s, this.z * s); }
    div(s) { return new Vec3(this.x / s, this.y / s, this.z / s); }
    dot(v) { return this.x * v.x + this.y * v.y + this.z * v.z; }
    
    cross(v) {
        return new Vec3(
            this.y * v.z - this.z * v.y,
            this.z * v.x - this.x * v.z,
            this.x * v.y - this.y * v.x
        );
    }

    length() { return Math.sqrt(this.dot(this)); }
    
    normalized() {
        const len = this.length();
        return len === 0 ? new Vec3() : this.div(len);
    }

    clone() { return new Vec3(this.x, this.y, this.z); }
}

export class ObjectData {
    constructor(position, radius, color, mass) {
        this.position = position; // Vec3
        this.radius = Number(radius);
        this.color = color; // [r, g, b, a] normalized 0-1
        this.mass = Number(mass);
        this.velocity = new Vec3();
    }
}

export class GravitySimulation {
    constructor(objects = []) {
        this.objects = objects;
    }

    step(enableGravity = true, timeStep = 1.0) {
        if (!enableGravity || this.objects.length === 0) return;

        const accelerations = this.objects.map(() => new Vec3());
        let anchorIndex = 0;
        let maxMass = -1;

        for (let i = 0; i < this.objects.length; i++) {
            if (this.objects[i].mass > maxMass) {
                maxMass = this.objects[i].mass;
                anchorIndex = i;
            }
        }

        for (let i = 0; i < this.objects.length; i++) {
            const objA = this.objects[i];
            for (let j = 0; j < this.objects.length; j++) {
                if (i === j) continue;
                const objB = this.objects[j];

                const offset = objB.position.sub(objA.position);
                const dist = Math.max(offset.length(), 1e9);
                const dir = offset.div(dist);
                const force = (G * objA.mass * objB.mass) / (dist * dist);
                accelerations[i] = accelerations[i].add(dir.mul((force / objA.mass) * timeStep));
            }
        }

        for (let i = 0; i < this.objects.length; i++) {
            if (i === anchorIndex) {
                this.objects[i].velocity = new Vec3();
                continue;
            }
            const obj = this.objects[i];
            obj.velocity = obj.velocity.add(accelerations[i]);
            obj.position = obj.position.add(obj.velocity.mul(timeStep));
        }
    }
}

/**
 * 3D Spacetime Grid deformed by gravity well (Flamm's paraboloid embedding diagram approximation)
 */
export class SpacetimeGrid {
    static generateMesh(objects, gridSize = 36, spacing = 2.5e10) {
        const vertices = [];
        const indices = [];

        const half = gridSize / 2;
        const gridPoints = [];

        for (let z = 0; z <= gridSize; z++) {
            const row = [];
            for (let x = 0; x <= gridSize; x++) {
                const wx = (x - half) * spacing;
                const wz = (z - half) * spacing;
                let height = 0.0;

                for (const obj of objects) {
                    const rs = (2.0 * G * obj.mass) / (C * C) * 1.5e5;
                    const dx = wx - obj.position.x;
                    const dz = wz - obj.position.z;
                    const dist = Math.sqrt(dx * dx + dz * dz);
                    
                    // Gravitational potential well funnel (Flamm's embedding diagram)
                    if (dist > rs) {
                        height -= (3.8 * rs) / Math.sqrt((dist / rs) + 0.2);
                    } else {
                        height -= 3.8 * rs;
                    }
                }

                row.push([wx, height, wz]);
            }
            gridPoints.push(row);
        }

        // Build vertex buffer & line indices
        for (let z = 0; z <= gridSize; z++) {
            for (let x = 0; x <= gridSize; x++) {
                const pt = gridPoints[z][x];
                vertices.push(pt[0], pt[1], pt[2]);

                const currIdx = z * (gridSize + 1) + x;
                if (x < gridSize) {
                    indices.push(currIdx, currIdx + 1);
                }
                if (z < gridSize) {
                    indices.push(currIdx, currIdx + (gridSize + 1));
                }
            }
        }

        return {
            vertices: new Float32Array(vertices),
            indices: new Uint16Array(indices)
        };
    }
}

/**
 * Geodesic Light Ray trajectory step calculator
 */
export class LightGeodesicIntegrator {
    static traceRayPath(startPos, startDir, schwarzschildRadius, steps = 180, stepSize = 1.2e8) {
        const path = [startPos.clone()];
        let pos = startPos.clone();
        let dir = startDir.normalized();

        for (let i = 0; i < steps; i++) {
            const r2 = pos.dot(pos);
            const r = Math.sqrt(r2);
            if (r <= schwarzschildRadius * 1.02) break; // Trapped in event horizon

            // Schwarzschild bending acceleration: a = - (1.5 * Rs / r^3) * (dir - pos*(pos.dot(dir)/r2))
            const impactDir = pos.div(r);
            const perp = dir.sub(impactDir.mul(dir.dot(impactDir)));
            const bendFactor = (1.8 * schwarzschildRadius) / (r2 + 1e-5);

            dir = dir.sub(impactDir.mul(bendFactor)).normalized();
            pos = pos.add(dir.mul(stepSize));
            path.push(pos.clone());

            if (r > schwarzschildRadius * 50) break; // Escaped into deep space
        }
        return path;
    }
}
