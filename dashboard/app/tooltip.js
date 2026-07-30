// The one shared tooltip element. Views must never create their own .tt node.
(function(A){
  let tt = document.getElementById("tt");
  if(!tt){
    tt = document.createElement("div");
    tt.className = "tt"; tt.id = "tt";
    document.body.appendChild(tt);
  }
  const moveTT = e => { tt.style.left = (e.clientX + 14) + "px"; tt.style.top = (e.clientY + 14) + "px"; };
  const showTT = (html, e) => { tt.innerHTML = html; tt.style.opacity = 1; moveTT(e); };
  const hideTT = () => { tt.style.opacity = 0; };
  A.tooltip = { showTT, moveTT, hideTT };
})(window.Atlas);
