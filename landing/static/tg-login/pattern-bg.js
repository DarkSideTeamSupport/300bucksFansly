/**
 * Анимированный фон как в Telegram Web K:
 * маленький gradient-canvas (50×50) + blend-canvas с pattern и soft-light.
 */
(function (global) {
	"use strict";

	const SIZE = 50;
	const TAILS = 90;
	const DEFAULT_COLORS = ["#dbddbb", "#6ba587", "#d5d88d", "#88b884"];
	const POSITIONS = [
		{ x: 0.8, y: 0.1 },
		{ x: 0.6, y: 0.2 },
		{ x: 0.35, y: 0.25 },
		{ x: 0.25, y: 0.6 },
		{ x: 0.2, y: 0.9 },
		{ x: 0.4, y: 0.8 },
		{ x: 0.65, y: 0.75 },
		{ x: 0.75, y: 0.4 },
	];

	function hexToRgb(hex) {
		const raw = String(hex || "").replace("#", "").trim();
		const full =
			raw.length === 3
				? raw
						.split("")
						.map((c) => c + c)
						.join("")
				: raw;
		const n = parseInt(full, 16);
		if (!Number.isFinite(n)) return { r: 0, g: 0, b: 0 };
		return { r: (n >> 16) & 255, g: (n >> 8) & 255, b: n & 255 };
	}

	class GradientRenderer {
		constructor() {
			this._width = SIZE;
			this._height = SIZE;
			this._tails = TAILS;
			this._positions = POSITIONS.map((p) => ({ ...p }));
			this._phases = this._positions.length;
			this._phase = 0;
			this._tail = 0;
			this._colors = [];
			this._hc = null;
			this._hctx = null;
			this._ctx = null;
			this._raf = 0;
			this._running = false;
			this._lastTs = 0;
		}

		init(canvas, colors) {
			this._colors = (colors && colors.length ? colors : DEFAULT_COLORS).map(hexToRgb);
			if (!this._hc) {
				this._hc = document.createElement("canvas");
				this._hc.width = this._width;
				this._hc.height = this._height;
				this._hctx = this._hc.getContext("2d", { alpha: false });
			}
			this._canvas = canvas;
			canvas.width = this._width;
			canvas.height = this._height;
			this._ctx = canvas.getContext("2d", { alpha: false });
			this._phase = 0;
			this._tail = 0;
			this.draw();
		}

		phasePositions(phase) {
			const out = [];
			for (let i = 0; i < 4; i++) {
				const p = this._positions[(phase + i * 2) % this._positions.length];
				out.push({ x: p.x, y: 1 - p.y });
			}
			return out;
		}

		getGradientImageData() {
			const { _width: w, _height: h, _colors: colors, _hctx: hctx } = this;
			const img = hctx.createImageData(w, h);
			const data = img.data;
			const a = colors.length;
			const next = this.phasePositions((this._phase + 1) % this._positions.length);
			const cur = this.phasePositions(this._phase);
			const t = 1 - this._tail / this._tails;
			let i = 0;

			for (let y = 0; y < h; y++) {
				const ny = y / h - 0.5;
				const ny2 = ny * ny;
				for (let x = 0; x < w; x++) {
					const nx = x / w - 0.5;
					const dist = 0.35 * Math.sqrt(nx * nx + ny2);
					const warp = dist * dist * 0.8 * 8;
					const s = Math.sin(warp);
					const c = Math.cos(warp);
					const px = Math.max(0, Math.min(1, 0.5 + nx * c - ny * s));
					const py = Math.max(0, Math.min(1, 0.5 + nx * s + ny * c));
					let wsum = 0;
					let r = 0;
					let g = 0;
					let b = 0;
					for (let k = 0; k < a; k++) {
						const cx = next[k].x + (cur[k].x - next[k].x) * t;
						const cy = next[k].y + (cur[k].y - next[k].y) * t;
						const dx = px - cx;
						const dy = py - cy;
						let o = Math.max(0, 0.9 - Math.sqrt(dx * dx + dy * dy));
						o = o * o * o * o;
						wsum += o;
						r += o * colors[k].r;
						g += o * colors[k].g;
						b += o * colors[k].b;
					}
					data[i++] = r / wsum;
					data[i++] = g / wsum;
					data[i++] = b / wsum;
					data[i++] = 255;
				}
			}
			return img;
		}

		draw() {
			if (!this._ctx || !this._hctx || this._colors.length < 2) return;
			const img = this.getGradientImageData();
			this._hctx.putImageData(img, 0, 0);
			this._ctx.drawImage(this._hc, 0, 0, this._width, this._height);
		}

		changeTail(delta) {
			this._tail += delta;
			while (this._tail >= this._tails) {
				this._tail -= this._tails;
				this._phase = (this._phase + 1) % this._phases;
			}
			while (this._tail < 0) {
				this._tail += this._tails;
				this._phase = (this._phase - 1 + this._phases) % this._phases;
			}
		}

		start() {
			if (this._running) return;
			this._running = true;
			this._lastTs = 0;
			const tick = (ts) => {
				if (!this._running) return;
				if (!this._lastTs) this._lastTs = ts;
				const dt = Math.min(48, ts - this._lastTs);
				this._lastTs = ts;
				// ~полный цикл фазы за ~12с при 60fps
				this.changeTail((dt / 16.67) * 0.12);
				this.draw();
				this._raf = requestAnimationFrame(tick);
			};
			this._raf = requestAnimationFrame(tick);
		}

		stop() {
			this._running = false;
			if (this._raf) {
				cancelAnimationFrame(this._raf);
				this._raf = 0;
			}
			this._lastTs = 0;
		}
	}

	function paintPattern(canvas, image) {
		const dpr = Math.min(2, window.devicePixelRatio || 1);
		const cssW = canvas.clientWidth || window.innerWidth;
		const cssH = canvas.clientHeight || window.innerHeight;
		canvas.width = Math.max(1, Math.round(cssW * dpr));
		canvas.height = Math.max(1, Math.round(cssH * dpr));
		const ctx = canvas.getContext("2d");
		if (!ctx || !image) return;
		ctx.clearRect(0, 0, canvas.width, canvas.height);
		const tileH = (500 + cssH / 2.5) * dpr;
		const scale = tileH / image.height;
		const tileW = image.width * scale;
		const drawRow = (y) => {
			for (let x = 0; x < canvas.width; x += tileW) {
				ctx.drawImage(image, x, y, tileW, tileH);
			}
		};
		let y = (canvas.height - tileH) / 2;
		drawRow(y);
		for (let up = y - tileH; up > -tileH; up -= tileH) drawRow(up);
		for (let down = y + tileH; down < canvas.height; down += tileH) drawRow(down);
	}

	class PatternBackground {
		constructor(root, options = {}) {
			this.root = root;
			this.colors = options.colors || DEFAULT_COLORS;
			this.patternUrl = options.patternUrl || "/static-landing/tg-login/pattern.svg";
			this.gradient = new GradientRenderer();
			this._patternImg = null;
			this._onResize = () => this._resizePattern();
			this._bound = false;
		}

		_ensureDom() {
			let layer = this.root.querySelector(".tg-auth__bg");
			if (layer) {
				this.layer = layer;
				this.gradientCanvas = layer.querySelector(".tg-auth__bg-gradient");
				this.blendCanvas = layer.querySelector(".tg-auth__bg-blend");
				return;
			}
			layer = document.createElement("div");
			layer.className = "tg-auth__bg";
			layer.setAttribute("aria-hidden", "true");
			layer.innerHTML =
				'<div class="tg-auth__bg-slot">' +
				'<canvas class="tg-auth__bg-canvas tg-auth__bg-gradient" width="50" height="50"></canvas>' +
				'<canvas class="tg-auth__bg-canvas tg-auth__bg-blend"></canvas>' +
				"</div>";
			this.root.insertBefore(layer, this.root.firstChild);
			this.layer = layer;
			this.gradientCanvas = layer.querySelector(".tg-auth__bg-gradient");
			this.blendCanvas = layer.querySelector(".tg-auth__bg-blend");
			if (this.gradientCanvas) {
				this.gradientCanvas.setAttribute("data-colors", this.colors.join(","));
			}
			if (this.blendCanvas) {
				this.blendCanvas.style.setProperty("--opacity-max", "0.5");
			}
		}

		_loadPattern() {
			if (this._patternImg) return Promise.resolve(this._patternImg);
			return new Promise((resolve, reject) => {
				const img = new Image();
				img.decoding = "async";
				img.onload = () => {
					this._patternImg = img;
					resolve(img);
				};
				img.onerror = reject;
				img.src = this.patternUrl;
			});
		}

		_resizePattern() {
			if (!this.blendCanvas || !this._patternImg) return;
			paintPattern(this.blendCanvas, this._patternImg);
		}

		async start() {
			if (!this.root) return;
			this._ensureDom();
			this.gradient.init(this.gradientCanvas, this.colors);
			try {
				await this._loadPattern();
				this._resizePattern();
			} catch (_) {
				/* gradient alone is enough */
			}
			if (!this._bound) {
				window.addEventListener("resize", this._onResize, { passive: true });
				this._bound = true;
			}
			this.gradient.start();
		}

		stop() {
			this.gradient.stop();
			if (this._bound) {
				window.removeEventListener("resize", this._onResize);
				this._bound = false;
			}
		}
	}

	global.TgPatternBackground = PatternBackground;
})(typeof window !== "undefined" ? window : globalThis);
