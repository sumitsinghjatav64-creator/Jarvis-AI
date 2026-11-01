/**
 * spring.js
 * Continuous Apple-grade spring physics solver.
 * Calculates exact trajectory with mass, stiffness, damping, and elastic overshoot.
 */

export class SpringProperty {
  constructor({ stiffness = 380, damping = 28, mass = 1.0, precision = 0.05 } = {}) {
    this.stiffness = stiffness;
    this.damping = damping;
    this.mass = mass;
    this.precision = precision;

    this.current = 0;
    this.target = 0;
    this.velocity = 0;
  }

  set(val) {
    this.current = val;
    this.target = val;
    this.velocity = 0;
  }

  setTarget(target) {
    this.target = target;
  }

  step(dt) {
    const displacement = this.current - this.target;
    const springForce = -this.stiffness * displacement;
    const dampingForce = -this.damping * this.velocity;
    const acceleration = (springForce + dampingForce) / this.mass;

    this.velocity += acceleration * dt;
    this.current += this.velocity * dt;

    const isResting = Math.abs(this.velocity) < this.precision && Math.abs(displacement) < this.precision;
    if (isResting) {
      this.current = this.target;
      this.velocity = 0;
    }
    return { value: this.current, resting: isResting };
  }
}

export class SpringAnimator {
  constructor(element, onUpdate) {
    this.element = element;
    this.onUpdate = onUpdate;
    this.props = {};
    this.rafId = null;
    this.lastTime = 0;
  }

  addProperty(name, initialValue, config) {
    const prop = new SpringProperty(config);
    prop.set(initialValue);
    this.props[name] = prop;
  }

  animateTo(targets) {
    for (const [key, val] of Object.entries(targets)) {
      if (this.props[key]) {
        this.props[key].setTarget(val);
      }
    }
    if (!this.rafId) {
      this.lastTime = performance.now();
      this.rafId = requestAnimationFrame(this._loop.bind(this));
    }
  }

  _loop(time) {
    const dt = Math.min((time - this.lastTime) / 1000, 0.032); // Clamp to avoid spikes
    this.lastTime = time;

    let allResting = true;
    const currentValues = {};

    for (const [key, prop] of Object.entries(this.props)) {
      const { value, resting } = prop.step(dt);
      currentValues[key] = value;
      if (!resting) allResting = false;
    }

    if (this.onUpdate) {
      this.onUpdate(currentValues);
    }

    if (!allResting) {
      this.rafId = requestAnimationFrame(this._loop.bind(this));
    } else {
      this.rafId = null;
    }
  }
}
