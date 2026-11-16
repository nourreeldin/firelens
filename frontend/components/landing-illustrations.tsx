export function OrbitalEarth() {
  return <svg className="landing-earth" viewBox="0 0 680 640" role="img" aria-label="Vector illustration of a satellite observing Earth, with orbital paths and illustrative fire observations over Africa">
    <defs>
      <radialGradient id="landing-atmosphere"><stop stopColor="#ebc28b" stopOpacity=".24" /><stop offset="1" stopColor="#ebc28b" stopOpacity="0" /></radialGradient>
      <radialGradient id="landing-ocean" cx="32%" cy="25%" r="85%"><stop stopColor="#2b4c63" /><stop offset=".65" stopColor="#172e43" /><stop offset="1" stopColor="#0c1e30" /></radialGradient>
      <linearGradient id="landing-land" x1="0" y1="0" x2="1" y2="1"><stop stopColor="#78908b" /><stop offset="1" stopColor="#3a5c63" /></linearGradient>
      <linearGradient id="landing-scan" x1="0" y1="0" x2="1" y2="1"><stop stopColor="#d88b44" stopOpacity=".02" /><stop offset="1" stopColor="#d88b44" stopOpacity=".25" /></linearGradient>
      <clipPath id="landing-earth-clip"><circle cx="350" cy="350" r="205" /></clipPath>
      <pattern id="landing-solar-cells" width="13" height="12" patternUnits="userSpaceOnUse"><rect width="13" height="12" fill="#203d56" /><path d="M0 0H13V12H0Z" fill="none" stroke="#8ba1ac" strokeWidth=".65" /></pattern>
    </defs>
    <circle cx="350" cy="350" r="285" fill="url(#landing-atmosphere)" />
    <g className="landing-orbital-grid" fill="none" stroke="currentColor" strokeWidth=".7" opacity=".26">
      <circle cx="350" cy="350" r="244" strokeDasharray="2 8" />
      <path d="M350 70V101M350 599V630M70 350H101M599 350H630" />
      <path d="M146 146l17 17M537 537l17 17M146 554l17-17M537 163l17-17" />
    </g>
    <ellipse cx="350" cy="350" rx="312" ry="111" transform="rotate(-32 350 350)" fill="none" stroke="#d88b44" strokeOpacity=".35" strokeWidth="1.1" strokeDasharray="5 7" />
    <path d="M139 128 268 299 421 288Z" fill="url(#landing-scan)" />
    <circle cx="350" cy="350" r="211" fill="none" stroke="#a8babd" strokeOpacity=".3" />
    <circle cx="350" cy="350" r="205" fill="url(#landing-ocean)" />
    <g clipPath="url(#landing-earth-clip)">
      <g fill="none" stroke="#a0b9c3" strokeWidth=".65" opacity=".17">
        {[135, 74].map((rx) => <ellipse key={rx} cx="350" cy="350" rx={rx} ry="205" />)}
        <path d="M350 145V555M145 350H555" />
        {[265, 435].map((cy) => <ellipse key={cy} cx="350" cy={cy} rx="210" ry="32" />)}
        {[195, 505].map((cy) => <ellipse key={cy} cx="350" cy={cy} rx="180" ry="27" />)}
      </g>
      <g fill="url(#landing-land)" stroke="#a3b2a1" strokeOpacity=".24" strokeWidth="1">
        <path d="m290 278 25-17 23 1 17 15 26-1 17 11 13 23 29 18 24 7-8 14-25 12-4 25-14 14-8 29-16 33-13 18-10-13-11-29-17-24-8-25-27-4-19-11-20 2-15-11-4-30 12-24Z" />
        <path d="m300 251 11-13 5-21 14-3 6-19 9-4 8 21-6 15 14 9 17-5 10-18 17 4 5 20 22 10 8 17 25-4 31 11 12 17 24 6 14 26 17 9 22 37-18 9-17-16-11-25-19-5-13 9-16-5-23 4-11-19-15-10-18-9-13-11-20 4-9-17-24-1-8 8Z" />
        <path d="m421 426 7 8-4 24-10 16-4-10 5-22Z" />
        <path d="m242 211 10-12 4-18 9-10 1 21-7 10-3 14-10 9Z" />
        <path d="m185 285-21 7-16 25 3 26 13 15 7 38 10 12 4 32 12 17 5-15-4-24 7-23-12-21 6-20-3-21 13-18-1-19Z" />
        <path d="m307 163 10-19 33-12 18 6-15 16-18 1-7 13Z" />
      </g>
      <g fill="#edb26b">
        {[[322, 292], [341, 290], [371, 298], [360, 328], [380, 372], [368, 405], [389, 433], [339, 364], [308, 327], [415, 310]].map(([x, y], i) => <g key={i}><circle cx={x} cy={y} r="9" opacity=".1" /><circle cx={x} cy={y} r="3" /></g>)}
      </g>
      <path d="M182 447C290 520 453 466 526 282" fill="none" stroke="#fff" strokeOpacity=".05" strokeWidth="46" />
    </g>
    <path d="M89 474C207 512 521 329 608 181" fill="none" stroke="#d88b44" strokeWidth="1.4" />
    <circle cx="608" cy="181" r="4" fill="#b35d27" />
    <g className="landing-satellite" transform="translate(143 126) rotate(-28)">
      <path d="M-66 0H66" stroke="#80919c" strokeWidth="3" />
      <rect x="-85" y="-22" width="59" height="44" rx="2" fill="url(#landing-solar-cells)" stroke="#637e92" />
      <rect x="26" y="-22" width="59" height="44" rx="2" fill="url(#landing-solar-cells)" stroke="#637e92" />
      <path d="m-18-24 36 2 5 44-39 4Z" fill="#d9d4c5" stroke="#a39782" strokeWidth="1.5" />
      <path d="m-18-24 10-9 37 3-11 8Z" fill="#f0e9d9" stroke="#a39782" strokeWidth="1.2" />
      <path d="m18-22 11-8 4 42-10 10Z" fill="#b1a98f" stroke="#a39782" strokeWidth="1.2" />
      <circle cy="3" r="9" fill="#263f52" stroke="#b35d27" strokeWidth="3" />
      <path d="M-6 26 0 40 9 26M0 40v10" fill="none" stroke="#a39782" strokeWidth="2" />
      <path d="M-8-34v-14m-7 4 7-4 7 4" fill="none" stroke="#7a8e9c" strokeWidth="1.5" />
    </g>
    <g className="landing-orbital-labels" fill="currentColor" fontFamily="ui-monospace, monospace" fontSize="9" letterSpacing="1.5">
      <text x="380" y="97">EARTH / ORBITAL PERSPECTIVE</text>
      <text x="27" y="570">OBSERVE. CONNECT. UNDERSTAND.</text>
    </g>
    <g fill="none" stroke="currentColor" opacity=".5">
      {[[586, 110], [90, 294], [570, 517], [249, 83], [98, 556]].map(([x, y], i) => <path key={i} d={`M${x - 4} ${y}h8m-4-4v8`} />)}
    </g>
    <g transform="translate(439 481)">
      <rect width="180" height="70" rx="7" className="landing-art-label" stroke="currentColor" strokeOpacity=".18" />
      <circle cx="20" cy="22" r="3" fill="#d88b44" />
      <text x="32" y="25" fill="currentColor" fontFamily="ui-monospace, monospace" fontSize="8" letterSpacing="1.1">FROM ORBIT TO INSIGHT</text>
      <path d="M19 49h20l6-7 7 12 8-17 8 12h21l7-5 6 5h29l6-12 6 12h17" fill="none" stroke="#b35d27" strokeWidth="1.4" />
    </g>
  </svg>;
}

export function SensorLayers() {
  return <svg viewBox="0 0 520 390" className="landing-sensor-illustration" role="img" aria-label="Illustration of MODIS and VIIRS observation grids connecting to a shared harmonized activity layer">
    <defs><pattern id="landing-layer-grid" width="28" height="28" patternUnits="userSpaceOnUse"><path d="M28 0H0V28" fill="none" stroke="currentColor" strokeOpacity=".16" /></pattern></defs>
    <g transform="translate(53 12)">
      <path d="m207 54 185 92-185 92L22 146Z" fill="var(--fl-surface)" stroke="var(--fl-border)" />
      <path d="m207 117 185 92-185 92L22 209Z" fill="var(--fl-fire-bg)" stroke="var(--fl-fire-border)" />
      <path d="m207 180 185 92-185 92L22 272Z" fill="var(--fl-surface)" stroke="var(--fl-border)" />
      <path d="M22 146v126m185-34v126m185-218v126" stroke="var(--fl-muted)" strokeOpacity=".35" strokeDasharray="3 5" />
      <g transform="translate(82 136) rotate(26.5) skewX(-37)">
        <rect width="203" height="95" fill="url(#landing-layer-grid)" />
        {[[28, 0], [84, 28], [112, 28], [56, 56], [140, 56]].map(([x, y], i) => <rect key={i} x={x} y={y} width="24" height="24" fill="#b35d27" opacity={i % 2 ? ".8" : ".4"} />)}
      </g>
      <path d="m148 258 14-4 14 9 17-7 14 12 18-4 17 9 16-4 16 11 18-5 17 8" fill="none" stroke="#b35d27" strokeWidth="3" />
    </g>
    <g fill="var(--fl-muted)" fontFamily="ui-monospace, monospace" fontSize="10" letterSpacing="1.5">
      <text x="57" y="64">MODIS</text><text x="401" y="102">VIIRS</text><text x="15" y="354">SHARED CONTEXT</text>
    </g>
    <path d="M105 61h63m226 38h-36M137 351h55" stroke="var(--fl-border)" />
    <circle cx="168" cy="61" r="3" fill="#b35d27" /><circle cx="358" cy="99" r="3" fill="#b35d27" />
  </svg>;
}

export function MapPreview() {
  return <svg viewBox="0 0 540 285" className="landing-map-preview" aria-hidden="true">
    <defs><pattern id="landing-map-grid" width="35" height="35" patternUnits="userSpaceOnUse"><path d="M35 0H0V35" fill="none" stroke="#b8c2c7" strokeOpacity=".25" strokeWidth=".7" /></pattern></defs>
    <rect width="540" height="285" fill="url(#landing-map-grid)" />
    <g fill="none" stroke="#81949d" strokeOpacity=".55" strokeWidth="1">
      <path d="m188 42 30-14 35 7 14 19 43 4 26 24 26 11 16 24 44 15-14 15-46 20-10 41-18 17-14 34-18 17-16-15-17-39-20-20-3-28-37-3-28-15-25 5-17-13-2-30 15-32Z" />
      <path d="m269 30 9-23 31-4 11 13 26-2 35 12 40 6 24 21 35 5 29 33-14 11-32-15-25 7-24-15-25 8-26-15-21 5-24-12-20 5Z" />
      <path d="m365 221 10-9 3 15-12 20-8-8Z" />
    </g>
    {[[216, 83], [246, 79], [278, 93], [312, 112], [273, 145], [290, 181], [301, 210], [282, 224], [245, 122], [335, 132]].map(([x, y], i) => <g key={i}><circle cx={x} cy={y} r="9" fill="#d88b44" opacity=".14" /><circle cx={x} cy={y} r={i % 3 ? 2.7 : 4} fill="#b35d27" /></g>)}
    <path d="M250 64v27m-13-14h27" stroke="#b35d27" strokeWidth=".8" opacity=".7" />
    <rect x="425" y="212" width="88" height="43" rx="5" fill="var(--fl-surface)" stroke="var(--fl-border)" />
    <path d="M440 226h12m-6-6v12m32-6h15m-15 17h15" stroke="var(--fl-muted)" />
  </svg>;
}

export function TrendPreview() {
  return <svg viewBox="0 0 320 96" className="landing-trend-preview" aria-hidden="true">
    <path d="M0 25H320M0 55H320M0 85H320" stroke="var(--fl-border)" strokeDasharray="3 5" />
    <path d="M0 76 20 73 38 62 57 66 78 40 98 48 117 26 138 36 159 17 180 42 199 35 219 58 240 51 259 67 280 59 301 72 320 62" fill="none" stroke="#b35d27" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
    <path d="M0 80 32 76 65 64 98 59 130 47 162 44 195 53 229 60 260 67 292 72 320 76" fill="none" stroke="#7d9aab" strokeWidth="1.5" strokeDasharray="5 5" />
  </svg>;
}
