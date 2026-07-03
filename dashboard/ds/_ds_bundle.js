/* @ds-bundle: {"format":4,"namespace":"TriadHealthEngineDesignSystem_0bb088","components":[{"name":"Alert","sourcePath":"components/core/Alert.jsx"},{"name":"Badge","sourcePath":"components/core/Badge.jsx"},{"name":"Button","sourcePath":"components/core/Button.jsx"},{"name":"Card","sourcePath":"components/core/Card.jsx"},{"name":"Checkbox","sourcePath":"components/core/Checkbox.jsx"},{"name":"Icon","sourcePath":"components/core/Icon.jsx"},{"name":"IconButton","sourcePath":"components/core/IconButton.jsx"},{"name":"Input","sourcePath":"components/core/Input.jsx"},{"name":"ProductBadge","sourcePath":"components/core/ProductBadge.jsx"},{"name":"Select","sourcePath":"components/core/Select.jsx"},{"name":"StatCard","sourcePath":"components/core/StatCard.jsx"},{"name":"Switch","sourcePath":"components/core/Switch.jsx"},{"name":"Tabs","sourcePath":"components/core/Tabs.jsx"},{"name":"Tag","sourcePath":"components/core/Tag.jsx"}],"sourceHashes":{"components/core/Alert.jsx":"3f6af3d5f5c2","components/core/Badge.jsx":"89e5435734ac","components/core/Button.jsx":"778e8a38c80b","components/core/Card.jsx":"006413f88dcb","components/core/Checkbox.jsx":"cd92bfa1ac9e","components/core/Icon.jsx":"e3811449bf35","components/core/IconButton.jsx":"6074e5dd5bd3","components/core/Input.jsx":"dccd0b39a4b8","components/core/ProductBadge.jsx":"9dbd612a9387","components/core/Select.jsx":"ee0b1730f8df","components/core/StatCard.jsx":"fb28419d83af","components/core/Switch.jsx":"fb595b6394ce","components/core/Tabs.jsx":"165c7e9d8f32","components/core/Tag.jsx":"836d4502ce36"},"inlinedExternals":[],"unexposedExports":[]} */

(() => {

const __ds_ns = (window.TriadHealthEngineDesignSystem_0bb088 = window.TriadHealthEngineDesignSystem_0bb088 || {});

const __ds_scope = {};

(__ds_ns.__errors = __ds_ns.__errors || []);

// components/core/Alert.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * Triad Health Engine — Alert
 * Inline message banner. tones: info, success, warning, danger.
 */
function Alert({
  children,
  title,
  tone = "info",
  icon = null,
  onClose,
  style = {},
  ...rest
}) {
  const tones = {
    info: {
      bg: "var(--info-50)",
      bd: "#bfdbfe",
      fg: "var(--info-700)"
    },
    success: {
      bg: "var(--success-50)",
      bd: "#a7f3d0",
      fg: "var(--success-700)"
    },
    warning: {
      bg: "var(--warning-50)",
      bd: "#fde68a",
      fg: "var(--warning-700)"
    },
    danger: {
      bg: "var(--danger-50)",
      bd: "#fecaca",
      fg: "var(--danger-700)"
    }
  };
  const t = tones[tone] || tones.info;
  return /*#__PURE__*/React.createElement("div", _extends({
    role: "status",
    style: {
      display: "flex",
      gap: 12,
      padding: "12px 14px",
      background: t.bg,
      border: `1px solid ${t.bd}`,
      borderRadius: "var(--radius-md)",
      ...style
    }
  }, rest), icon && /*#__PURE__*/React.createElement("span", {
    style: {
      color: t.fg,
      display: "inline-flex",
      marginTop: 1
    }
  }, icon), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1
    }
  }, title && /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: "var(--font-sans)",
      fontSize: "14px",
      fontWeight: "var(--fw-semibold)",
      color: t.fg,
      marginBottom: children ? 2 : 0
    }
  }, title), children && /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: "var(--font-sans)",
      fontSize: "13px",
      color: "var(--text-body)",
      lineHeight: "var(--lh-normal)"
    }
  }, children)), onClose && /*#__PURE__*/React.createElement("button", {
    onClick: onClose,
    "aria-label": "Dismiss",
    style: {
      border: "none",
      background: "transparent",
      color: t.fg,
      cursor: "pointer",
      fontSize: 18,
      lineHeight: 1,
      padding: 0
    }
  }, "\xD7"));
}
Object.assign(__ds_scope, { Alert });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Alert.jsx", error: String((e && e.message) || e) }); }

// components/core/Badge.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * Triad Health Engine — Badge
 * Small status label. tones: neutral, brand, success, warning, danger, info.
 */
function Badge({
  children,
  tone = "neutral",
  subtle = true,
  style = {},
  ...rest
}) {
  const tones = {
    neutral: subtle ? {
      bg: "var(--slate-100)",
      fg: "var(--slate-700)"
    } : {
      bg: "var(--slate-700)",
      fg: "#fff"
    },
    brand: subtle ? {
      bg: "var(--brand-subtle)",
      fg: "var(--violet-700)"
    } : {
      bg: "var(--brand)",
      fg: "#fff"
    },
    success: subtle ? {
      bg: "var(--success-50)",
      fg: "var(--success-700)"
    } : {
      bg: "var(--success-500)",
      fg: "#fff"
    },
    warning: subtle ? {
      bg: "var(--warning-50)",
      fg: "var(--warning-700)"
    } : {
      bg: "var(--warning-500)",
      fg: "#fff"
    },
    danger: subtle ? {
      bg: "var(--danger-50)",
      fg: "var(--danger-700)"
    } : {
      bg: "var(--danger-500)",
      fg: "#fff"
    },
    info: subtle ? {
      bg: "var(--info-50)",
      fg: "var(--info-700)"
    } : {
      bg: "var(--info-500)",
      fg: "#fff"
    }
  };
  const t = tones[tone] || tones.neutral;
  return /*#__PURE__*/React.createElement("span", _extends({
    style: {
      display: "inline-flex",
      alignItems: "center",
      padding: "2px 8px",
      borderRadius: "var(--radius-pill)",
      fontFamily: "var(--font-sans)",
      fontSize: "12px",
      fontWeight: "var(--fw-semibold)",
      lineHeight: 1.4,
      background: t.bg,
      color: t.fg,
      ...style
    }
  }, rest), children);
}
Object.assign(__ds_scope, { Badge });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Badge.jsx", error: String((e && e.message) || e) }); }

// components/core/Button.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * Triad Health Engine — Button
 * Variants: primary (brand violet), secondary (slate outline), ghost, danger.
 * Sizes: sm, md, lg. Optional leading/trailing icon nodes.
 */
function Button({
  children,
  variant = "primary",
  size = "md",
  disabled = false,
  fullWidth = false,
  iconLeft = null,
  iconRight = null,
  type = "button",
  onClick,
  style = {},
  ...rest
}) {
  const sizes = {
    sm: {
      fontSize: "13px",
      padding: "6px 12px",
      height: 32,
      gap: 6
    },
    md: {
      fontSize: "15px",
      padding: "9px 16px",
      height: 40,
      gap: 8
    },
    lg: {
      fontSize: "16px",
      padding: "12px 22px",
      height: 48,
      gap: 8
    }
  };
  const variants = {
    primary: {
      background: "var(--brand)",
      color: "var(--brand-on)",
      border: "1px solid var(--brand)"
    },
    secondary: {
      background: "var(--surface-card)",
      color: "var(--text-strong)",
      border: "1px solid var(--border-default)"
    },
    ghost: {
      background: "transparent",
      color: "var(--text-body)",
      border: "1px solid transparent"
    },
    danger: {
      background: "var(--danger-500)",
      color: "#fff",
      border: "1px solid var(--danger-500)"
    }
  };
  const s = sizes[size] || sizes.md;
  const v = variants[variant] || variants.primary;
  const [hover, setHover] = React.useState(false);
  const [active, setActive] = React.useState(false);
  const hoverBg = {
    primary: active ? "var(--brand-active)" : "var(--brand-hover)",
    secondary: "var(--surface-sunken)",
    ghost: "var(--surface-sunken)",
    danger: active ? "var(--danger-700)" : "#dc2626"
  }[variant];
  return /*#__PURE__*/React.createElement("button", _extends({
    type: type,
    disabled: disabled,
    onClick: onClick,
    onMouseEnter: () => setHover(true),
    onMouseLeave: () => {
      setHover(false);
      setActive(false);
    },
    onMouseDown: () => setActive(true),
    onMouseUp: () => setActive(false),
    style: {
      display: "inline-flex",
      alignItems: "center",
      justifyContent: "center",
      gap: s.gap,
      width: fullWidth ? "100%" : "auto",
      height: s.height,
      padding: s.padding,
      fontFamily: "var(--font-sans)",
      fontSize: s.fontSize,
      fontWeight: "var(--fw-semibold)",
      lineHeight: 1,
      borderRadius: "var(--radius-md)",
      cursor: disabled ? "not-allowed" : "pointer",
      opacity: disabled ? 0.5 : 1,
      transition: "var(--transition-control)",
      boxShadow: variant === "primary" ? "var(--shadow-xs)" : "none",
      ...v,
      ...(hover && !disabled ? {
        background: hoverBg,
        borderColor: variant === "secondary" ? "var(--border-strong)" : undefined
      } : {}),
      ...style
    }
  }, rest), iconLeft, children, iconRight);
}
Object.assign(__ds_scope, { Button });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Button.jsx", error: String((e && e.message) || e) }); }

// components/core/Card.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * Triad Health Engine — Card
 * Base surface: white, 12px radius, hairline border + soft shadow.
 */
function Card({
  children,
  padding = 20,
  interactive = false,
  style = {},
  ...rest
}) {
  const [hover, setHover] = React.useState(false);
  return /*#__PURE__*/React.createElement("div", _extends({
    onMouseEnter: () => interactive && setHover(true),
    onMouseLeave: () => interactive && setHover(false),
    style: {
      background: "var(--surface-card)",
      border: "1px solid var(--border-subtle)",
      borderRadius: "var(--radius-lg)",
      boxShadow: hover ? "var(--shadow-md)" : "var(--shadow-sm)",
      padding,
      transition: "box-shadow var(--dur-base) var(--ease-out), border-color var(--dur-base) var(--ease-out)",
      cursor: interactive ? "pointer" : "default",
      ...(hover ? {
        borderColor: "var(--border-default)"
      } : {}),
      ...style
    }
  }, rest), children);
}
Object.assign(__ds_scope, { Card });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Card.jsx", error: String((e && e.message) || e) }); }

// components/core/Checkbox.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * Triad Health Engine — Checkbox
 */
function Checkbox({
  checked,
  defaultChecked = false,
  onChange,
  disabled = false,
  label,
  style = {},
  ...rest
}) {
  const [internal, setInternal] = React.useState(defaultChecked);
  const on = checked !== undefined ? checked : internal;
  const toggle = () => {
    if (disabled) return;
    if (checked === undefined) setInternal(!on);
    onChange && onChange(!on);
  };
  return /*#__PURE__*/React.createElement("label", {
    style: {
      display: "inline-flex",
      alignItems: "center",
      gap: 10,
      cursor: disabled ? "not-allowed" : "pointer",
      opacity: disabled ? 0.5 : 1
    }
  }, /*#__PURE__*/React.createElement("span", _extends({
    role: "checkbox",
    "aria-checked": on,
    onClick: toggle,
    style: {
      width: 18,
      height: 18,
      borderRadius: "var(--radius-xs)",
      border: on ? "1px solid var(--brand)" : "1px solid var(--border-strong)",
      background: on ? "var(--brand)" : "var(--surface-card)",
      display: "inline-flex",
      alignItems: "center",
      justifyContent: "center",
      transition: "var(--transition-control)",
      ...style
    }
  }, rest), on && /*#__PURE__*/React.createElement("svg", {
    width: "12",
    height: "12",
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "#fff",
    strokeWidth: "3.5",
    strokeLinecap: "round",
    strokeLinejoin: "round"
  }, /*#__PURE__*/React.createElement("polyline", {
    points: "20 6 9 17 4 12"
  }))), label && /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: "var(--font-sans)",
      fontSize: "14px",
      color: "var(--text-body)"
    }
  }, label));
}
Object.assign(__ds_scope, { Checkbox });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Checkbox.jsx", error: String((e && e.message) || e) }); }

// components/core/Icon.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * Triad Health Engine — Icon
 * Thin wrapper over Lucide (https://lucide.dev). Loads the Lucide UMD global and
 * renders the named glyph as an inline SVG using currentColor. Outline style,
 * ~1.75px stroke — matches Triad's clinical, precise tone.
 *
 * NOTE: Lucide is a substitution (no brand icon set was provided). Requires the
 * Lucide UMD script on the page: https://unpkg.com/lucide@latest
 */
function toPascal(name) {
  return String(name).split(/[-_\s]+/).filter(Boolean).map(w => w.charAt(0).toUpperCase() + w.slice(1)).join("");
}
function Icon({
  name,
  size = 20,
  strokeWidth = 1.75,
  color = "currentColor",
  style = {},
  ...rest
}) {
  const set = typeof window !== "undefined" && window.lucide && window.lucide.icons || {};
  let node = set[toPascal(name)] || set[name];
  if (node && node.default) node = node.default;
  // Lucide IconNode: array of [tag, attrs] children (may be nested under [2]).
  let children = Array.isArray(node) ? node : null;
  if (children && children.length === 3 && typeof children[0] === "string" && Array.isArray(children[2])) {
    children = children[2]; // [tag, attrs, children] form
  }
  return /*#__PURE__*/React.createElement("svg", _extends({
    width: size,
    height: size,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: color,
    strokeWidth: strokeWidth,
    strokeLinecap: "round",
    strokeLinejoin: "round",
    style: {
      display: "inline-block",
      flexShrink: 0,
      verticalAlign: "middle",
      ...style
    },
    "aria-hidden": "true"
  }, rest), children ? children.map((c, i) => Array.isArray(c) ? React.createElement(c[0], {
    key: i,
    ...(c[1] || {})
  }) : null) : null);
}
Object.assign(__ds_scope, { Icon });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Icon.jsx", error: String((e && e.message) || e) }); }

// components/core/IconButton.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * Triad Health Engine — IconButton
 * Square icon-only button. variants: ghost, secondary, primary.
 */
function IconButton({
  children,
  label,
  variant = "ghost",
  size = "md",
  disabled = false,
  onClick,
  style = {},
  ...rest
}) {
  const [hover, setHover] = React.useState(false);
  const dim = size === "sm" ? 32 : size === "lg" ? 44 : 40;
  const variants = {
    ghost: {
      background: "transparent",
      color: "var(--text-body)",
      border: "1px solid transparent",
      hoverBg: "var(--surface-sunken)"
    },
    secondary: {
      background: "var(--surface-card)",
      color: "var(--text-strong)",
      border: "1px solid var(--border-default)",
      hoverBg: "var(--surface-sunken)"
    },
    primary: {
      background: "var(--brand)",
      color: "#fff",
      border: "1px solid var(--brand)",
      hoverBg: "var(--brand-hover)"
    }
  };
  const v = variants[variant] || variants.ghost;
  return /*#__PURE__*/React.createElement("button", _extends({
    type: "button",
    "aria-label": label,
    title: label,
    disabled: disabled,
    onClick: onClick,
    onMouseEnter: () => setHover(true),
    onMouseLeave: () => setHover(false),
    style: {
      width: dim,
      height: dim,
      display: "inline-flex",
      alignItems: "center",
      justifyContent: "center",
      borderRadius: "var(--radius-md)",
      cursor: disabled ? "not-allowed" : "pointer",
      opacity: disabled ? 0.5 : 1,
      transition: "var(--transition-control)",
      background: hover && !disabled ? v.hoverBg : v.background,
      color: v.color,
      border: v.border,
      ...style
    }
  }, rest), children);
}
Object.assign(__ds_scope, { IconButton });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/IconButton.jsx", error: String((e && e.message) || e) }); }

// components/core/Input.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * Triad Health Engine — Input
 * Labeled text field with optional leading icon, hint, and error state.
 */
function Input({
  label,
  hint,
  error,
  iconLeft = null,
  id,
  style = {},
  containerStyle = {},
  ...rest
}) {
  const [focus, setFocus] = React.useState(false);
  const inputId = id || (label ? "in-" + label.replace(/\s+/g, "-").toLowerCase() : undefined);
  const borderColor = error ? "var(--danger-500)" : focus ? "var(--border-focus)" : "var(--border-default)";
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexDirection: "column",
      gap: 6,
      ...containerStyle
    }
  }, label && /*#__PURE__*/React.createElement("label", {
    htmlFor: inputId,
    style: {
      fontFamily: "var(--font-sans)",
      fontSize: "13px",
      fontWeight: "var(--fw-medium)",
      color: "var(--text-body)"
    }
  }, label), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      gap: 8,
      height: 40,
      padding: "0 12px",
      background: "var(--surface-card)",
      border: `1px solid ${borderColor}`,
      borderRadius: "var(--radius-md)",
      boxShadow: focus ? "var(--shadow-focus)" : "none",
      transition: "var(--transition-control)"
    }
  }, iconLeft && /*#__PURE__*/React.createElement("span", {
    style: {
      color: "var(--text-subtle)",
      display: "inline-flex"
    }
  }, iconLeft), /*#__PURE__*/React.createElement("input", _extends({
    id: inputId,
    onFocus: () => setFocus(true),
    onBlur: () => setFocus(false),
    style: {
      flex: 1,
      minWidth: 0,
      border: "none",
      outline: "none",
      background: "transparent",
      fontFamily: "var(--font-sans)",
      fontSize: "15px",
      color: "var(--text-strong)",
      ...style
    }
  }, rest))), (hint || error) && /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: "var(--font-sans)",
      fontSize: "12px",
      color: error ? "var(--danger-700)" : "var(--text-muted)"
    }
  }, error || hint));
}
Object.assign(__ds_scope, { Input });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Input.jsx", error: String((e && e.message) || e) }); }

// components/core/ProductBadge.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * Triad Health Engine — ProductBadge
 * Labeled chip for one of the four products, tinted with its signature accent.
 */
const PRODUCTS = {
  signal: {
    label: "Signal",
    bg: "var(--signal-50)",
    fg: "var(--signal-600)",
    dot: "var(--signal-500)"
  },
  rev: {
    label: "Rev",
    bg: "var(--rev-50)",
    fg: "var(--rev-600)",
    dot: "var(--rev-500)"
  },
  core: {
    label: "Core",
    bg: "var(--core-50)",
    fg: "var(--core-600)",
    dot: "var(--core-500)"
  },
  command: {
    label: "Command",
    bg: "var(--command-50)",
    fg: "var(--command-600)",
    dot: "var(--command-500)"
  }
};
function ProductBadge({
  product = "core",
  size = "md",
  solid = false,
  style = {},
  ...rest
}) {
  const p = PRODUCTS[product] || PRODUCTS.core;
  const sm = size === "sm";
  return /*#__PURE__*/React.createElement("span", _extends({
    style: {
      display: "inline-flex",
      alignItems: "center",
      gap: sm ? 5 : 6,
      padding: sm ? "3px 8px" : "4px 10px",
      borderRadius: "var(--radius-pill)",
      fontFamily: "var(--font-sans)",
      fontSize: sm ? "12px" : "13px",
      fontWeight: "var(--fw-semibold)",
      lineHeight: 1,
      letterSpacing: "0.01em",
      background: solid ? p.dot : p.bg,
      color: solid ? "#fff" : p.fg,
      ...style
    }
  }, rest), /*#__PURE__*/React.createElement("span", {
    style: {
      width: sm ? 6 : 7,
      height: sm ? 6 : 7,
      borderRadius: "50%",
      background: solid ? "#fff" : p.dot
    }
  }), p.label);
}
Object.assign(__ds_scope, { ProductBadge });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/ProductBadge.jsx", error: String((e && e.message) || e) }); }

// components/core/Select.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * Triad Health Engine — Select
 * Styled native <select> with label + optional icon.
 */
function Select({
  label,
  options = [],
  value,
  onChange,
  disabled = false,
  id,
  containerStyle = {},
  style = {},
  ...rest
}) {
  const [focus, setFocus] = React.useState(false);
  const selId = id || (label ? "sel-" + label.replace(/\s+/g, "-").toLowerCase() : undefined);
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexDirection: "column",
      gap: 6,
      ...containerStyle
    }
  }, label && /*#__PURE__*/React.createElement("label", {
    htmlFor: selId,
    style: {
      fontFamily: "var(--font-sans)",
      fontSize: "13px",
      fontWeight: "var(--fw-medium)",
      color: "var(--text-body)"
    }
  }, label), /*#__PURE__*/React.createElement("div", {
    style: {
      position: "relative",
      display: "flex"
    }
  }, /*#__PURE__*/React.createElement("select", _extends({
    id: selId,
    value: value,
    disabled: disabled,
    onChange: e => onChange && onChange(e.target.value),
    onFocus: () => setFocus(true),
    onBlur: () => setFocus(false),
    style: {
      appearance: "none",
      WebkitAppearance: "none",
      width: "100%",
      height: 40,
      padding: "0 36px 0 12px",
      fontFamily: "var(--font-sans)",
      fontSize: "15px",
      color: "var(--text-strong)",
      background: "var(--surface-card)",
      border: `1px solid ${focus ? "var(--border-focus)" : "var(--border-default)"}`,
      borderRadius: "var(--radius-md)",
      boxShadow: focus ? "var(--shadow-focus)" : "none",
      cursor: disabled ? "not-allowed" : "pointer",
      opacity: disabled ? 0.5 : 1,
      outline: "none",
      transition: "var(--transition-control)",
      ...style
    }
  }, rest), options.map(o => {
    const val = typeof o === "string" ? o : o.value;
    const lab = typeof o === "string" ? o : o.label;
    return /*#__PURE__*/React.createElement("option", {
      key: val,
      value: val
    }, lab);
  })), /*#__PURE__*/React.createElement("span", {
    style: {
      position: "absolute",
      right: 12,
      top: "50%",
      transform: "translateY(-50%)",
      pointerEvents: "none",
      color: "var(--text-muted)"
    }
  }, /*#__PURE__*/React.createElement("svg", {
    width: "16",
    height: "16",
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "2",
    strokeLinecap: "round",
    strokeLinejoin: "round"
  }, /*#__PURE__*/React.createElement("polyline", {
    points: "6 9 12 15 18 9"
  })))));
}
Object.assign(__ds_scope, { Select });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Select.jsx", error: String((e && e.message) || e) }); }

// components/core/StatCard.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * Triad Health Engine — StatCard
 * Metric tile: eyebrow label, big mono figure, optional delta + product accent.
 */
function StatCard({
  label,
  value,
  unit,
  delta,
  deltaDir = "up",
  accent = "brand",
  icon = null,
  style = {},
  ...rest
}) {
  const accents = {
    brand: "var(--brand)",
    signal: "var(--signal-600)",
    rev: "var(--rev-600)",
    core: "var(--core-600)",
    command: "var(--command-600)"
  };
  const deltaColor = deltaDir === "up" ? "var(--success-700)" : deltaDir === "down" ? "var(--danger-700)" : "var(--text-muted)";
  return /*#__PURE__*/React.createElement("div", _extends({
    style: {
      background: "var(--surface-card)",
      border: "1px solid var(--border-subtle)",
      borderRadius: "var(--radius-lg)",
      boxShadow: "var(--shadow-sm)",
      padding: 18,
      display: "flex",
      flexDirection: "column",
      gap: 10,
      ...style
    }
  }, rest), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between"
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: "var(--font-sans)",
      fontSize: "12px",
      fontWeight: "var(--fw-semibold)",
      letterSpacing: "var(--ls-label)",
      textTransform: "uppercase",
      color: "var(--text-muted)"
    }
  }, label), icon && /*#__PURE__*/React.createElement("span", {
    style: {
      color: accents[accent] || accents.brand,
      display: "inline-flex"
    }
  }, icon)), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "baseline",
      gap: 6
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: "var(--font-mono)",
      fontVariantNumeric: "tabular-nums",
      fontSize: "30px",
      fontWeight: "var(--fw-semibold)",
      color: "var(--text-strong)",
      lineHeight: 1
    }
  }, value), unit && /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: "var(--font-sans)",
      fontSize: "14px",
      color: "var(--text-muted)"
    }
  }, unit)), delta != null && /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: "var(--font-mono)",
      fontSize: "12px",
      fontWeight: "var(--fw-medium)",
      color: deltaColor
    }
  }, deltaDir === "up" ? "▲" : deltaDir === "down" ? "▼" : "•", " ", delta));
}
Object.assign(__ds_scope, { StatCard });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/StatCard.jsx", error: String((e && e.message) || e) }); }

// components/core/Switch.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * Triad Health Engine — Switch (toggle)
 */
function Switch({
  checked,
  defaultChecked = false,
  onChange,
  disabled = false,
  label,
  id,
  style = {},
  ...rest
}) {
  const [internal, setInternal] = React.useState(defaultChecked);
  const on = checked !== undefined ? checked : internal;
  const toggle = () => {
    if (disabled) return;
    if (checked === undefined) setInternal(!on);
    onChange && onChange(!on);
  };
  const sw = /*#__PURE__*/React.createElement("button", _extends({
    role: "switch",
    "aria-checked": on,
    "aria-label": typeof label === "string" ? label : undefined,
    disabled: disabled,
    onClick: toggle,
    style: {
      width: 40,
      height: 24,
      borderRadius: "var(--radius-pill)",
      border: "none",
      padding: 2,
      background: on ? "var(--brand)" : "var(--slate-300)",
      cursor: disabled ? "not-allowed" : "pointer",
      opacity: disabled ? 0.5 : 1,
      transition: "background-color var(--dur-base) var(--ease-out)",
      display: "inline-flex",
      alignItems: "center",
      ...style
    }
  }, rest), /*#__PURE__*/React.createElement("span", {
    style: {
      width: 20,
      height: 20,
      borderRadius: "50%",
      background: "#fff",
      boxShadow: "var(--shadow-sm)",
      transform: on ? "translateX(16px)" : "translateX(0)",
      transition: "transform var(--dur-base) var(--ease-out)"
    }
  }));
  if (!label) return sw;
  return /*#__PURE__*/React.createElement("label", {
    style: {
      display: "inline-flex",
      alignItems: "center",
      gap: 10,
      cursor: disabled ? "not-allowed" : "pointer"
    }
  }, sw, /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: "var(--font-sans)",
      fontSize: "14px",
      color: "var(--text-body)"
    }
  }, label));
}
Object.assign(__ds_scope, { Switch });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Switch.jsx", error: String((e && e.message) || e) }); }

// components/core/Tabs.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * Triad Health Engine — Tabs
 * Underline tab bar. Controlled or uncontrolled.
 * items: [{ id, label, badge? }]
 */
function Tabs({
  items = [],
  value,
  defaultValue,
  onChange,
  style = {},
  ...rest
}) {
  const [internal, setInternal] = React.useState(defaultValue ?? (items[0] && items[0].id));
  const active = value !== undefined ? value : internal;
  const select = id => {
    if (value === undefined) setInternal(id);
    onChange && onChange(id);
  };
  return /*#__PURE__*/React.createElement("div", _extends({
    role: "tablist",
    style: {
      display: "flex",
      gap: 4,
      borderBottom: "1px solid var(--border-subtle)",
      ...style
    }
  }, rest), items.map(it => {
    const on = it.id === active;
    return /*#__PURE__*/React.createElement("button", {
      key: it.id,
      role: "tab",
      "aria-selected": on,
      onClick: () => select(it.id),
      style: {
        display: "inline-flex",
        alignItems: "center",
        gap: 7,
        padding: "10px 12px",
        border: "none",
        background: "transparent",
        cursor: "pointer",
        fontFamily: "var(--font-sans)",
        fontSize: "14px",
        fontWeight: on ? "var(--fw-semibold)" : "var(--fw-medium)",
        color: on ? "var(--text-strong)" : "var(--text-muted)",
        borderBottom: on ? "2px solid var(--brand)" : "2px solid transparent",
        marginBottom: -1,
        transition: "var(--transition-control)"
      }
    }, it.label, it.badge != null && /*#__PURE__*/React.createElement("span", {
      style: {
        fontFamily: "var(--font-mono)",
        fontSize: "11px",
        fontWeight: "var(--fw-medium)",
        color: on ? "var(--violet-700)" : "var(--text-subtle)",
        background: on ? "var(--brand-subtle)" : "var(--slate-100)",
        borderRadius: "var(--radius-pill)",
        padding: "1px 7px"
      }
    }, it.badge));
  }));
}
Object.assign(__ds_scope, { Tabs });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Tabs.jsx", error: String((e && e.message) || e) }); }

// components/core/Tag.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * Triad Health Engine — Tag
 * Filter/keyword chip, optionally removable. Neutral by default; accepts a color.
 */
function Tag({
  children,
  onRemove,
  color,
  icon = null,
  style = {},
  ...rest
}) {
  return /*#__PURE__*/React.createElement("span", _extends({
    style: {
      display: "inline-flex",
      alignItems: "center",
      gap: 6,
      height: 26,
      padding: "0 4px 0 10px",
      borderRadius: "var(--radius-sm)",
      border: "1px solid var(--border-subtle)",
      background: "var(--surface-sunken)",
      fontFamily: "var(--font-sans)",
      fontSize: "13px",
      fontWeight: "var(--fw-medium)",
      color: color || "var(--text-body)",
      ...style
    }
  }, rest), icon, /*#__PURE__*/React.createElement("span", {
    style: {
      padding: onRemove ? 0 : "0 6px 0 0"
    }
  }, children), onRemove && /*#__PURE__*/React.createElement("button", {
    onClick: onRemove,
    "aria-label": "Remove",
    style: {
      display: "inline-flex",
      alignItems: "center",
      justifyContent: "center",
      width: 18,
      height: 18,
      border: "none",
      background: "transparent",
      color: "var(--text-subtle)",
      cursor: "pointer",
      borderRadius: "var(--radius-xs)"
    }
  }, /*#__PURE__*/React.createElement("svg", {
    width: "12",
    height: "12",
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "2.5",
    strokeLinecap: "round"
  }, /*#__PURE__*/React.createElement("line", {
    x1: "18",
    y1: "6",
    x2: "6",
    y2: "18"
  }), /*#__PURE__*/React.createElement("line", {
    x1: "6",
    y1: "6",
    x2: "18",
    y2: "18"
  }))));
}
Object.assign(__ds_scope, { Tag });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Tag.jsx", error: String((e && e.message) || e) }); }

__ds_ns.Alert = __ds_scope.Alert;

__ds_ns.Badge = __ds_scope.Badge;

__ds_ns.Button = __ds_scope.Button;

__ds_ns.Card = __ds_scope.Card;

__ds_ns.Checkbox = __ds_scope.Checkbox;

__ds_ns.Icon = __ds_scope.Icon;

__ds_ns.IconButton = __ds_scope.IconButton;

__ds_ns.Input = __ds_scope.Input;

__ds_ns.ProductBadge = __ds_scope.ProductBadge;

__ds_ns.Select = __ds_scope.Select;

__ds_ns.StatCard = __ds_scope.StatCard;

__ds_ns.Switch = __ds_scope.Switch;

__ds_ns.Tabs = __ds_scope.Tabs;

__ds_ns.Tag = __ds_scope.Tag;

})();
