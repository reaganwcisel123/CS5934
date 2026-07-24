/* Landing page behavior: tessellation canvas, scroll reveals, count-ups. No libraries.
   JS only adds motion; the HTML is complete without it, and reduced motion is honored. */
(function () {
  "use strict";

  var reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // Announce JS so CSS may hide .reveal elements; a no-JS visitor never sees hidden content.
  document.documentElement.classList.add("js");

  /* ================= 1. Tessellation hero canvas ================= */
  function tessellation() {
    var canvas = document.getElementById("lp-mesh");
    if (!canvas || !canvas.getContext) return;
    var ctx = canvas.getContext("2d");

    var SPACING = 96;
    var JITTER = 13;
    var MOUSE_R = 190;
    var PUSH = 34;

    var pts = [], tris = [], w = 0, h = 0, raf = 0;
    var mx = -9999, my = -9999;

    // Deterministic jitter: identical across rebuilds, organic to the eye.
    function hash(c, r) {
      var s = Math.sin(c * 12.9898 + r * 78.233) * 43758.5453;
      return s - Math.floor(s);
    }

    function build() {
      var host = canvas.parentElement;
      w = host.clientWidth; h = host.clientHeight;
      var dpr = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = w * dpr; canvas.height = h * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

      // Staggered triangular grid: equilateral row height, odd rows offset half a spacing.
      pts = []; tris = [];
      var rowH = SPACING * 0.866;
      var cols = Math.ceil(w / SPACING) + 2;
      var rows = Math.ceil(h / rowH) + 2;
      var grid = [];
      for (var r = 0; r < rows; r++) {
        grid[r] = [];
        for (var c = 0; c < cols; c++) {
          var x = c * SPACING + (r % 2 ? SPACING / 2 : 0) - SPACING / 2;
          var y = r * rowH - rowH / 2;
          x += (hash(c, r) - 0.5) * 2 * JITTER;
          y += (hash(r, c) - 0.5) * 2 * JITTER;
          var p = { bx: x, by: y, x: x, y: y, gold: pts.length % 23 === 0 };
          grid[r][c] = p; pts.push(p);
        }
      }
      // Two triangles per grid cell; the diagonal alternates by row parity.
      for (r = 0; r < rows - 1; r++) {
        for (c = 0; c < cols - 1; c++) {
          var a = grid[r][c], b = grid[r][c + 1], d = grid[r + 1][c], e = grid[r + 1][c + 1];
          if (r % 2) { tris.push([a, b, d], [b, e, d]); }
          else { tris.push([a, b, e], [a, e, d]); }
        }
      }
    }

    // Push points away from the cursor (quadratic falloff), then lerp toward target.
    function step() {
      for (var i = 0; i < pts.length; i++) {
        var p = pts[i];
        var tx = p.bx, ty = p.by;
        var dx = p.bx - mx, dy = p.by - my;
        var dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < MOUSE_R && dist > 0.001) {
          var f = 1 - dist / MOUSE_R;
          var push = PUSH * f * f;
          tx += (dx / dist) * push;
          ty += (dy / dist) * push;
        }
        p.x += (tx - p.x) * 0.12;
        p.y += (ty - p.y) * 0.12;
      }
    }

    function near(x, y) {
      var dx = x - mx, dy = y - my;
      var dist = Math.sqrt(dx * dx + dy * dy);
      return dist > MOUSE_R ? 0 : 1 - dist / MOUSE_R;
    }

    // Triangles first (fill/brighten near the cursor), then nodes on top.
    function draw() {
      ctx.clearRect(0, 0, w, h);
      for (var i = 0; i < tris.length; i++) {
        var t = tris[i];
        var cx = (t[0].x + t[1].x + t[2].x) / 3;
        var cy = (t[0].y + t[1].y + t[2].y) / 3;
        var n = near(cx, cy);
        ctx.beginPath();
        ctx.moveTo(t[0].x, t[0].y);
        ctx.lineTo(t[1].x, t[1].y);
        ctx.lineTo(t[2].x, t[2].y);
        ctx.closePath();
        if (n > 0) {
          ctx.fillStyle = "rgba(139, 92, 246, " + (0.1 * n).toFixed(3) + ")";
          ctx.fill();
        }
        ctx.strokeStyle = "rgba(150, 135, 225, " + (0.1 + 0.3 * n).toFixed(3) + ")";
        ctx.lineWidth = 1;
        ctx.stroke();
      }
      for (i = 0; i < pts.length; i++) {
        var p = pts[i];
        var pn = near(p.x, p.y);
        ctx.beginPath();
        if (p.gold) {
          ctx.arc(p.x, p.y, 2.2 + pn * 1.2, 0, Math.PI * 2);
          ctx.fillStyle = "rgba(245, 158, 11, " + (0.55 + 0.45 * pn).toFixed(3) + ")";
        } else {
          ctx.arc(p.x, p.y, 1.3 + pn * 0.9, 0, Math.PI * 2);
          ctx.fillStyle = "rgba(160, 145, 230, " + (0.4 + 0.4 * pn).toFixed(3) + ")";
        }
        ctx.fill();
      }
    }

    function loop() { step(); draw(); raf = requestAnimationFrame(loop); }

    build();
    if (reduced) { draw(); window.addEventListener("resize", function () { build(); draw(); }); return; }

    var onMove = function (e) {
      var rect = canvas.getBoundingClientRect();
      mx = e.clientX - rect.left; my = e.clientY - rect.top;
    };
    var onLeave = function () { mx = -9999; my = -9999; };
    canvas.parentElement.addEventListener("pointermove", onMove);
    canvas.parentElement.addEventListener("pointerleave", onLeave);
    window.addEventListener("resize", build);
    loop();
    window.addEventListener("pagehide", function () { cancelAnimationFrame(raf); });
  }

  /* ================= 2. Scroll reveals ================= */
  function reveals() {
    var els = Array.prototype.slice.call(document.querySelectorAll(".reveal"));
    if (!els.length) return;
    var show = function (el) { el.classList.add("in"); };
    if (reduced || !("IntersectionObserver" in window)) { els.forEach(show); return; }
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (en.isIntersecting) { show(en.target); io.unobserve(en.target); }
      });
    }, { threshold: 0.15 });
    els.forEach(function (el) { io.observe(el); });
    // Failsafe: a stalled observer (headless browsers) must never leave the page blank.
    setTimeout(function () { els.forEach(show); }, 2500);
  }

  /* ================= 3. Count-up stats ================= */
  function countUps() {
    // Markup is the source of truth: <span data-count="133">0</span>, suffix as a static sibling.
    var els = Array.prototype.slice.call(document.querySelectorAll("[data-count]"));
    if (!els.length) return;
    var render = function (el, v) {
      var target = el.getAttribute("data-count");
      var decimals = target.indexOf(".") >= 0 ? target.split(".")[1].length : 0;
      var prefix = el.getAttribute("data-prefix") || "";
      el.textContent = prefix + v.toFixed(decimals);
    };
    var finish = function (el) { render(el, parseFloat(el.getAttribute("data-count"))); };
    if (reduced || !("IntersectionObserver" in window)) { els.forEach(finish); return; }
    // 1.3 s tween with cubic ease-out.
    var run = function (el) {
      var target = parseFloat(el.getAttribute("data-count"));
      var t0 = null, DUR = 1300;
      var tick = function (ts) {
        if (!t0) t0 = ts;
        var p = Math.min((ts - t0) / DUR, 1);
        var eased = 1 - Math.pow(1 - p, 3);
        render(el, target * eased);
        if (p < 1) requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    };
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (en.isIntersecting) { run(en.target); io.unobserve(en.target); }
      });
    }, { threshold: 0.4 });
    els.forEach(function (el) { io.observe(el); });
    setTimeout(function () { els.forEach(function (el) { if (el.textContent === "0") finish(el); }); }, 3000);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () { tessellation(); reveals(); countUps(); });
  } else {
    tessellation(); reveals(); countUps();
  }
})();
