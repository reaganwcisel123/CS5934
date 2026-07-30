// Self-contained inline-SVG icon set (24x24 strokes, currentColor by default).
// Replaces both the DS-bundle Icon and its unpinned lucide@latest dependency.
(function(A){
  const P = {
    "info": ["<circle cx='12' cy='12' r='9'/>", "<path d='M12 8h.01M12 11v5'/>"],
    "gauge": ["<path d='M12 15l3.5-5'/>", "<path d='M20.2 17a9 9 0 1 0-16.4 0'/>", "<circle cx='12' cy='15' r='1.4'/>"],
    "map-pin": ["<path d='M12 21s-7-5.3-7-11a7 7 0 0 1 14 0c0 5.7-7 11-7 11z'/>", "<circle cx='12' cy='10' r='2.5'/>"],
    "activity": ["<path d='M2 12h4l2 8 4-16 3 8h7'/>"],
    "alert-triangle": ["<path d='M12 3 2.5 20h19L12 3z'/>", "<path d='M12 9v5M12 17.5h.01'/>"],
    "layers": ["<path d='M12 3 2 8.5 12 14l10-5.5L12 3z'/>", "<path d='m2 13 10 5.5L22 13'/>"],
    "brain": ["<path d='M9.5 3A2.5 2.5 0 0 0 7 5.5v.6A3.5 3.5 0 0 0 4.5 9.5c0 .7.2 1.4.6 2A3.5 3.5 0 0 0 4 14.5 3.5 3.5 0 0 0 7.5 18c.2 1.7 1.5 3 3 3 .8 0 1.5-.5 1.5-1.5v-14C12 4 11 3 9.5 3z'/>", "<path d='M14.5 3A2.5 2.5 0 0 1 17 5.5v.6a3.5 3.5 0 0 1 2.5 3.4c0 .7-.2 1.4-.6 2a3.5 3.5 0 0 1 1.1 3A3.5 3.5 0 0 1 16.5 18c-.2 1.7-1.5 3-3 3-.8 0-1.5-.5-1.5-1.5v-14C12 4 13 3 14.5 3z'/>"],
    "user-check": ["<circle cx='9' cy='8' r='4'/>", "<path d='M2 21c0-3.5 3-6 7-6 1.4 0 2.7.3 3.8.9'/>", "<path d='m15 17 2.5 2.5L22 15'/>"],
    "clipboard-check": ["<rect x='5' y='4' width='14' height='17' rx='2'/>", "<path d='M9 4a2 2 0 0 1 6 0'/>", "<path d='m8.5 13.5 2.5 2.5 4.5-4.5'/>"],
    "grid-3x3": ["<rect x='3' y='3' width='18' height='18' rx='2'/>", "<path d='M3 9h18M3 15h18M9 3v18M15 3v18'/>"],
    "scatter-chart": ["<path d='M3 3v18h18'/>", "<circle cx='9' cy='9' r='1.6'/>", "<circle cx='15' cy='6' r='1.6'/>", "<circle cx='13' cy='14' r='1.6'/>", "<circle cx='18' cy='11' r='1.6'/>"],
    "target": ["<circle cx='12' cy='12' r='9'/>", "<circle cx='12' cy='12' r='5'/>", "<circle cx='12' cy='12' r='1'/>"],
    "message-circle": ["<path d='M21 12a8.5 8.5 0 0 1-8.5 8.5c-1.5 0-3-.4-4.2-1.1L3 21l1.6-5.3A8.5 8.5 0 1 1 21 12z'/>"],
    "sparkles": ["<path d='M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9L12 3z'/>", "<path d='M19 15l.9 2.1L22 18l-2.1.9L19 21l-.9-2.1L16 18l2.1-.9L19 15z'/>"],
    "send": ["<path d='M22 2 11 13'/>", "<path d='M22 2 15 22l-4-9-9-4 20-7z'/>"],
    "x": ["<path d='M18 6 6 18M6 6l12 12'/>"],
    "search": ["<circle cx='11' cy='11' r='7'/>", "<path d='m21 21-4.3-4.3'/>"],
    "chevron-down": ["<path d='m6 9 6 6 6-6'/>"],
    "arrow-right": ["<path d='M5 12h14M13 6l6 6-6 6'/>"],
    "compass": ["<circle cx='12' cy='12' r='9'/>", "<path d='m15.5 8.5-2 5-5 2 2-5 5-2z'/>"],
    "map": ["<path d='M3 6.5 9 4l6 2.5 6-2.5v15L15 21l-6-2.5L3 21z'/>", "<path d='M9 4v14.5M15 6.5V21'/>"],
    "git-branch": ["<circle cx='6' cy='5' r='2'/>", "<circle cx='6' cy='19' r='2'/>", "<circle cx='18' cy='12' r='2'/>", "<path d='M6 7v10M6 9a6 6 0 0 0 6 6h4'/>"],
    "heart-pulse": ["<path d='M12 20s-7-4.35-9.5-9A5.5 5.5 0 0 1 12 5.5 5.5 5.5 0 0 1 21.5 11c-.6 1.2-1.4 2.3-2.3 3.4'/>", "<path d='M3 12h4l2-4 3 7 2-5 1 2h6'/>"],
    "list-checks": ["<path d='m3 5 1.5 1.5L7 4'/>", "<path d='m3 12 1.5 1.5L7 11'/>", "<path d='m3 19 1.5 1.5L7 18'/>", "<path d='M11 6h10M11 13h10M11 20h10'/>"],
    "trending-up": ["<path d='m3 17 6-6 4 4 8-8'/>", "<path d='M15 7h6v6'/>"],
    "book-open": ["<path d='M2 4h7a3 3 0 0 1 3 3v13a3 3 0 0 0-3-3H2V4z'/>", "<path d='M22 4h-7a3 3 0 0 0-3 3v13a3 3 0 0 1 3-3h7V4z'/>"],
    "calendar": ["<rect x='3' y='5' width='18' height='16' rx='2'/>", "<path d='M8 3v4M16 3v4M3 10h18'/>"],
    "help-circle": ["<circle cx='12' cy='12' r='9'/>", "<path d='M9.5 9a2.5 2.5 0 0 1 4.9.8c0 1.6-2.4 2.2-2.4 3.7'/>", "<path d='M12 17h.01'/>"],
  };
  function Icon({ name, size = 18, color = "currentColor" }){
    const paths = P[name] || ["<circle cx='12' cy='12' r='8'/>"];
    return (
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color}
        strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"
        dangerouslySetInnerHTML={{ __html: paths.join("") }} />
    );
  }
  A.Icon = Icon;
})(window.Atlas);
