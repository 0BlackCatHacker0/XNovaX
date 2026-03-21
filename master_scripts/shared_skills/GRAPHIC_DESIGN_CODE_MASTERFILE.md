====================================================================
GRAPHIC DESIGN CODE MASTERFILE
A practical, copy/paste-ready reference for generating, editing,
automating, and exporting graphic design assets across common pipelines.
====================================================================

CONTENTS
1) Vector Graphics (SVG) â€” shapes, icons, logos, text, filters
2) Web Graphics â€” HTML/CSS templates, Canvas 2D, WebGL
3) Motion Graphics â€” Lottie, SVG/Canvas animation, FFmpeg recipes
4) Color Systems â€” palettes, conversions, accessibility checks
5) Typography â€” variable fonts, font loading, responsive type scales
6) Layout Systems â€” grids, spacing, constraints, design tokens
7) Image Processing â€” ImageMagick, FFmpeg, Python (Pillow), batch ops
8) 3D/Render Design Adjacent â€” Blender scripting hooks, sprite sheets
9) Tool Automation â€” Adobe scripts, Inkscape CLI, Figma plugins
10) File Output & Packaging â€” naming, export presets, pipeline hygiene

--------------------------------------------------------------------
1) VECTOR GRAPHICS (SVG)
--------------------------------------------------------------------

1.1 Minimal SVG template
```svg
<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="1024" viewBox="0 0 1024 1024">
  <rect width="100%" height="100%" fill="#0b0f14"/>
  <circle cx="512" cy="512" r="220" fill="#00ff9c" opacity="0.9"/>
  <text x="512" y="560" text-anchor="middle" font-family="Inter, Arial" font-size="96" fill="#bfffe9">
    NOVA
  </text>
</svg>
```

1.2 Reusable icon system (stroke-based, scalable)
```svg
<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128" viewBox="0 0 24 24" fill="none">
  <path d="M4 12h16" stroke="#00ff9c" stroke-width="2" stroke-linecap="round"/>
  <path d="M12 4v16" stroke="#00ff9c" stroke-width="2" stroke-linecap="round"/>
</svg>
```

1.3 Gradients + glow (filter)
```svg
<svg xmlns="http://www.w3.org/2000/svg" width="600" height="300" viewBox="0 0 600 300">
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#00ff9c"/>
      <stop offset="100%" stop-color="#00d0ff"/>
    </linearGradient>
    <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
      <feGaussianBlur stdDeviation="6" result="b"/>
      <feMerge>
        <feMergeNode in="b"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>
  </defs>
  <rect x="60" y="60" width="480" height="180" rx="28" fill="url(#g)" filter="url(#glow)"/>
</svg>
```

1.4 SVG export notes
- Prefer viewBox for responsive scaling.
- Convert text to outlines for print-safe logos (unless you need editability).
- Keep strokes consistent: use vector effect `non-scaling-stroke` if needed.

--------------------------------------------------------------------
2) WEB GRAPHICS: HTML/CSS TEMPLATES, CANVAS 2D, WEBGL
--------------------------------------------------------------------

2.1 Glass UI card (HTML/CSS)
```html
<div class="card">
  <h2>Glass Panel</h2>
  <p>Neon border + blur.</p>
</div>
<style>
  body{margin:0;min-height:100vh;display:grid;place-items:center;background:#060b10;color:#bfffe9;font-family:system-ui}
  .card{
    width:min(720px,92vw); padding:24px 28px; border-radius:22px;
    background:rgba(10,20,25,.45);
    border:1px solid rgba(0,255,180,.35);
    box-shadow:0 0 25px rgba(0,255,180,.25), inset 0 0 18px rgba(0,255,180,.15);
    backdrop-filter:blur(18px);
  }
</style>
```

2.2 Canvas 2D: noise gradient background
```html
<canvas id="c"></canvas>
<script>
const c=document.getElementById('c'), ctx=c.getContext('2d');
function resize(){c.width=innerWidth; c.height=innerHeight} addEventListener('resize',resize); resize();
function rnd(n){return Math.floor(Math.random()*n)}
function draw(){
  const img=ctx.createImageData(c.width,c.height);
  for(let i=0;i<img.data.length;i+=4){
    const v = 8 + rnd(24); // grain
    img.data[i]=v; img.data[i+1]=v+8; img.data[i+2]=v+14; img.data[i+3]=255;
  }
  ctx.putImageData(img,0,0);
  requestAnimationFrame(draw);
}
draw();
</script>
```

2.3 WebGL fragment shader (neon glow field)
```glsl
// fragment.glsl
precision highp float;
uniform vec2 u_res;
uniform float u_time;
float glow(vec2 p){
  float d = length(p);
  return 0.02/(d*d+0.001);
}
void main(){
  vec2 uv=(gl_FragCoord.xy/u_res)-0.5;
  uv.x*=u_res.x/u_res.y;
  float g=glow(uv + 0.04*sin(u_time+uv.yx*6.0));
  vec3 col = vec3(0.0,1.0,0.65)*g + vec3(0.0,0.8,1.0)*g*0.6;
  gl_FragColor = vec4(col,1.0);
}
```

--------------------------------------------------------------------
3) MOTION GRAPHICS
--------------------------------------------------------------------

3.1 Lottie (JSON animation) notes
- Use After Effects + Bodymovin export
- Keep shapes simple; avoid unsupported effects
- Optimize with lottie-web + gzip

3.2 CSS keyframes: glow pulse
```css
@keyframes pulse {
  0%,100% { box-shadow: 0 0 18px rgba(0,255,180,.20); }
  50%     { box-shadow: 0 0 34px rgba(0,255,180,.45); }
}
.pulse { animation: pulse 2.2s ease-in-out infinite; }
```

3.3 FFmpeg: turn image sequence into MP4
```bash
ffmpeg -framerate 30 -i frames_%04d.png -c:v libx264 -pix_fmt yuv420p out.mp4
```

3.4 FFmpeg: GIF from MP4 (high quality)
```bash
ffmpeg -i in.mp4 -vf "fps=18,scale=720:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse" out.gif
```

--------------------------------------------------------------------
4) COLOR SYSTEMS
------------------------------------------------------------------KB‚ŒH^8¡¥‘Ğˆ]ZXÚÈÛÛ™\œÚ[Ûˆ
”ÊB˜œÂ™[˜İ[Ûˆ^Ô™ØŠ^
^ÂˆÛÛœİZ^œ™\XÙJ	ÈÉË	ÉÊNÂˆÛÛœİ\\œÙR[
›[™İOOLÏÈœÜ]
	ÉÊK›X\
O
Ş
Kš›Ú[Š	ÉÊHˆMŠNÂˆ™]\›ˆÜŠŒMŠIŒMKÎŠ
IŒMK›‰ŒM_NÂŸB˜‚ŒˆĞĞQÈÛÛ˜\İ
”ÊB˜œÂ™[˜İ[Ûˆ[Z[˜[˜ÙJÜ‹ËŸJ^ÂˆÛÛœİOVÜ‹Ë—K›X\
OÂˆ‹ÏLMNÈ™]\›ˆLŒÎLÈ‹ÌL‹LˆˆX]œİÊ
ŠÌŒMJKÌKŒMK‹
NÂˆJNÂˆ™]\›ˆŒŒLŠ˜VÌJÌÌMLŠ˜VÌWJÌŒÌŒŠ˜VÌ—NÂŸB™[˜İ[ÛˆÛÛ˜\İ
^K^Š^ÂˆÛÛœİO[[Z[˜[˜ÙJ^Ô™ØŠ^JJJÌŒNÂˆÛÛœİ[[Z[˜[˜ÙJ^Ô™ØŠ^ŠJJÌŒNÂˆ™]\›ˆO“ÈKÓˆˆ‹ÓNÂŸB˜‚ŒÈ˜XİXØ[[]H]\›‚‹H˜XÚÙÜ›İ[™ˆHY\™]]˜[‹H›Ü™YÜ›İ[™ˆHYÚ™]]˜[‹HXØÙ[Nˆ™[Û‹Øœ˜[™‹HXØÙ[ˆÙXÛÛ™\HYÚYÚ‹H[\ˆ™YÜ[šÂ‚‹KKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKBJHTÑÔTB‹KKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKB‚KŒHÔÔÎˆ˜\šXX›H›Û[\Ü˜ÜÜÂ›ÛY˜XÙHÂˆ›ÛY˜[Z[Nˆ’[\•˜\ˆÂˆÜ˜Îˆ\›
’[\‹U˜\šXX›Q›ÛÜÛÙÚˆŠH›Ü›X]
Y]\HŠNÂˆ›Û]ÙZYÚˆLLÂˆ›Û\İ[Nˆ›Ü›X[ÂŸBœ›ÛİÈKX˜\ÙNˆÛ[\
MœKŒ]ËN
NÈB˜›ÙHÈ›ÛY˜[Z[Nˆ[\•˜\‹Ş\İ[K]ZNÈ›Û\Ú^™Nˆ˜\ŠKX˜\ÙJNÈBšHÈ›Û\Ú^™NˆÛ[\
ÌœİËMœ
NÈ]\‹\ÜXÚ[™Î‹LŒ™[NÈB˜‚KŒˆ\HØØ[HÙ[™\˜]Üˆ
˜][ËX˜\ÙY
B‹HXÚÈ˜\ÙNˆMœ‹H˜][ÎˆKŒˆ
İXJHÈKŒH
İ[™\™
HÈKŒÌÌÈ
˜[X]XÊB‹H]™[ÎˆËÛK˜\ÙKËŞ‚‹KKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKBŠHVSÕUÖTÕSTÈ	ˆTÒQÓˆÒÑS”Â‹KKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKB‚‹ŒHÚÙ[ˆš[H
”ÓÓŠB˜œÛÛ‚Âˆ˜ÛÛÜˆˆÂˆ˜™ÈˆˆÌŒŒL‹ˆ™™ÈˆˆØ™™™™NH‹ˆ˜XØÙ[ˆˆÌ™XÈ‹ˆ˜XØÙ[ˆˆˆÌ™ˆ‹ˆ™[™Ù\ˆˆˆÙ™ŒØ˜ˆ‚ˆKˆœ˜Y]\ÈˆÈœÛHˆL›YˆN›ÈˆˆKˆœÚYİÈˆÈ™ÛİÈˆŒ\™Ø˜JMKNŒJHˆKˆœÜXÙHˆÈŒHˆŒˆˆŒÈˆL‹ˆM‹HˆˆˆÌˆBŸB˜‚‹ŒˆÔÔÈ˜\šXX›\Èœ›ÛHÚÙ[œÂ˜ÜÜÂœ›ÛİÂˆKX™ÎˆÌŒŒLÈKY™ÎˆØ™™™™NNÈKXNˆÌ™XÎÈKXˆÌ™ÈKY[™Ù\ˆÙ™ŒØ˜ÂˆK\‹[YŒNÈK\ËMŒMœÂŸB˜‚‹ŒÈÜšY]ZXÚÈ[\Â‹HÜXÚ[™ÈŞ\İ[B‹H\ÙHX^ÚYÛÛZ[™\œÈ
K™Ë‹LŒ
B‹H^[İ]ˆL‹XÛÛ[[ˆÜšYÛˆ\ÚİÜÍˆÛˆ[Øš[B‚‹KKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKBÊHSPQÑH“ĞÑTÔÒS‘È
UÒ
B‹KKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKB‚ËŒH[XYÙSXYÚXÚÎˆ™\Ú^™KÚ\œ[‹[™İš\Y]Y]B˜˜\Ú›XYÚXÚÈ[œ]œ™È\™\Ú^™HŒŒˆ][œÚ\œKŒ\İš\İ]]œ™Â˜‚ËŒˆ[XYÙSXYÚXÚÎˆÛÛ™\‘È8¡¤ˆÙX”˜˜\Ú›XYÚXÚÈ[œ]œ™È\]X[]HLİ]]ÙXœ˜‚ËŒÈ[XYÙSXYÚXÚÎˆ˜]ÚÛÛ™\›Û\‚˜˜\Ú›XYÚXÚÈ[ÙÜšYH\]İ]Y›Ü›X]ÙXœ\]X[]H
‹œ™Â˜‚Ë]Ûˆ
[İÊNˆ˜]Ú™\Ú^™B˜]Û‚™œ›ÛHS[\Ü[XYÙB™œ›ÛH]Xˆ[\Ü]œÜ˜ÏT]
š[ˆŠNÈİT]
›İ]ŠNÈİ›ZÙ\Š^\İÛÚÏUYJB™›Üˆ[ˆÜ˜Ë™ÛØŠŠ‹œ™ÈŠN‚ˆ[OR[XYÙK›Ü[Š
K˜ÛÛ™\
”‘ĞHŠBˆ[K[X›˜Z[

ŒŒ
JBˆ[KœØ]™JİÊœİ[JÈ‹œ™ÈŠKÜ[Z^™OUYJB˜‚‹KKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKB
HÑÈ‘S‘TˆTÒQÓˆQPÑS•‹KKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKB‚ŒH›[™\ˆ™[™\ˆ\›X›Hœ˜[Y\È
]ÛŠB˜]Û‚š[\ÜœKX]œØÙ[™OXœK˜ÛÛ^œØÙ[™B™›ÜˆH[ˆ˜[™ÙJLŒ
N‚ˆØÙ[™K™œ˜[YWÜÙ]
JBˆØÙ[™K˜Ø[Y\˜Kœ›İ][Û—Ù][\–Ì—O[X]œ˜YX[œÊJŒËŒ
BˆØÙ[™Kœ™[™\‹™š[\]Yˆ‹ËÙœ˜[Y\ËÙœ˜[YWŞÚNŒKœ™È‚ˆœK›ÜËœ™[™\‹œ™[™\ŠÜš]WÜİ[UYJB˜‚ŒˆÜš]HÚY]›İ\Â‹H™[™\ˆ˜[œÜ\™[‘Èœ˜[Y\Â‹HXÚÈÚ]^\™TXÚÙ\‹Ğ\Ù\š]KĞÓHÛÛÂ‹HÙY\İÙ\‹[Ù‹]ÛÈÚ^™\È›ÜˆÔ\ÈÚ[ˆ™YYY‚‹KKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKBJHÓÓUUÓPUSÓ‚‹KKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKB‚KŒH[šÜØØ\HÓNˆ^ÜÕ‘È8¡¤ˆ‘È]˜˜\Úš[šÜØØ\H[œ]œİ™ÈKY^Ü]\O\™ÈKY^ÜYOLNLˆKY^ÜYš[[˜[YO[İ]œ™Â˜‚KŒˆYØ™H[\İ˜]Üˆ^[™ØÜš\ˆ^Ü\›Ø\™ÂŠ\ÙH[\İ˜]ÜˆØÜš\[™È[™[ÈÚÙ[]ÛŠB˜œÂ‹ËÈÙ]YÎˆ]\˜]H\›Ø\™Ë^Ü‘Â˜‚KŒÈšYÛXHYÚ[ˆ˜\ÚXÜÂ‹HRH[ˆS‹HYÚ[ˆÛÙH[ˆÂ‹H\ÙHšYÛXK˜Ü™X]T™Xİ[™ÛJ
KšYÛXK™^Ü\Ş[˜Ê
B‚‹KKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKBŒL
H’SHÕUUSRS‘ËPÒĞQÒS‘Â‹KKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKB‚ŒLŒH˜[Z[™ÈÛÛ™[[ÛœÈ
İX›H\[[™\ÊBTÔÑUÏĞUQÓÔ–O—ÏSQO—ÏÒV‘O—ÏT’PS•—İˆÈÈË™^‘^[\\Î‚TÔÑUÒPÓÓ—Ó›İ˜VÌÛ[™WİŒKœİ™ÂTÔÑUĞ‘×ÓX]š^ÌÎŒMŒİŒËœ™ÂTÔÑUÓÑÓ×ÍŒ[™×ÌLÙš[İŒL‹œİ™Â‚ŒLŒˆ^Ü™\Ù]Â•ÙX‚‹HÕ‘È›ÜˆXÛÛœËÛÙÛÜÂ‹HÙX”ĞU’Qˆ›ÜˆİÜÂ‹H‘È›Üˆ˜[œÜ\™[˜ŞB”š[‚‹H‹ÖÚ\™HÜÜÚX›B‹HÌH˜\İ\‚‹HÓVRÈÛÛ™\œÚ[Ûˆ]š[˜[İYÙB‚ŒLŒÈY]Y]HYÚY[™B‹Hİš\VQˆ›ÜˆX›XÈ™[X\Ù\Â‹HÙY\Ûİ\˜ÙHš[\ÈÙ\\˜]H
ÔËÊB‹H^Ü[ÈTÕÂ‚‹KKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKB”URPÒÈÕT•ˆ•RSHÑÓÈ
ÈÓĞÒPSPÒÈSˆHÓÓSPS‘Â‹KKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKBŒJH\ÚYÛˆ™XİÜˆ[ˆÕ‘È
ÔËÛÙÛËœİ™ÊBŒŠH^Ü‘ÜÎ‚ˆ[šÜØØ\HÔËÛÙÛËœİ™ÈKY^Ü]\O\™ÈKY^ÜYOLNLˆKY^ÜYš[[˜[YOQTÕÛÙÛ×Ìœ™ÂŒÊHXZÙHÙX”‚ˆXYÚXÚÈTÕÛÙÛ×Ìœ™È\]X[]HLTÕÛÙÛ×ÌÙXœ
HÜ™X]H˜[›™\ˆ˜\šX[Î‚ˆXYÚXÚÈTÕÛÙÛ×Ìœ™È\™\Ú^™HMŒMˆYÜ˜]š]HÙ[\ˆY^[MŒMTÕØ˜[›™\‹œ™ÂJHXÚØYÙN‚ˆš\\ˆTÕĞTÔÑUÔPÒ×İŒKš\TÕÂ‚‘S‘ÑˆPTÕT‘’SB