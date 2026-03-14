// 背景地図の定義
const BASEMAPS = {
  'gsi-pale': {
    label: '地理院 淡色',
    icon: '🎨',
    tiles: ['https://cyberjapandata.gsi.go.jp/xyz/pale/{z}/{x}/{y}.png'],
    attribution: '<a href="https://maps.gsi.go.jp/development/ichiran.html">国土地理院</a>',
    tileSize: 256,
    maxzoom: 18,
  },
  'gsi-std': {
    label: '地理院 標準',
    icon: '📍',
    tiles: ['https://cyberjapandata.gsi.go.jp/xyz/std/{z}/{x}/{y}.png'],
    attribution: '<a href="https://maps.gsi.go.jp/development/ichiran.html">国土地理院</a>',
    tileSize: 256,
    maxzoom: 18,
  },
  'gsi-alt': {
    label: '地理院 標高図',
    icon: '🏔',
    tiles: ['https://cyberjapandata.gsi.go.jp/xyz/relief/{z}/{x}/{y}.png'],
    attribution: '<a href="https://maps.gsi.go.jp/development/ichiran.html">国土地理院</a>',
    tileSize: 256,
    maxzoom: 18,
  }
};

const DEFAULT_BASEMAP = 'gsi-pale';

// 名山データ 可視化モードの定義
const VIZ_MODES = {
  category: {
    label: '種別',
    paint: {
      'circle-color': [
        'step', ['get', 'no'],
        '#e74c3c',          // 百名山   (No.1-100)
        101, '#f39c12',     // 二百名山 (No.101-200)
        201, '#3498db',     // 三百名山 (No.201+)
      ],
      'circle-radius': 6,
      'circle-stroke-width': 1.5,
      'circle-stroke-color': '#fff',
      'circle-opacity': 0.9,
    },
  },
  elevation: {
    label: '標高',
    paint: {
      'circle-color': [
        'interpolate', ['linear'], ['get', 'elev_m'],
        500,  '#ffffcc',
        1500, '#feb24c',
        2500, '#f03b20',
        3800, '#800026',
      ],
      'circle-radius': 6,
      'circle-stroke-width': 1.5,
      'circle-stroke-color': '#fff',
      'circle-opacity': 0.9,
    },
  },
  count: {
    label: '登頂回数',
    paint: {
      'circle-color': [
        'case',
        ['>', ['coalesce', ['get', 'count'], 0], 0], '#3366ff',
        '#cccccc',
      ],
      'circle-radius': [
        'interpolate', ['linear'], ['coalesce', ['get', 'count'], 0],
        0, 5,
        1, 8,
        3, 11,
      ],
      'circle-stroke-width': 1.5,
      'circle-stroke-color': '#fff',
      'circle-opacity': 0.9,
    },
  },
};

// 泉質リスト
const SPRING_TYPES = [
  '単純温泉', '塩化物泉', '炭酸水素塩泉', '硫酸塩泉',
  '二酸化炭素泉', '含鉄泉', '含ヨウ素塩泉', '酸性泉', '硫黄泉', '放射能泉',
];

const SPRING_ACTIVE_COLOR = '#e07b00';   // 入湯あり（泉質一致 or フィルタなし）
const SPRING_UNVISITED_COLOR = '#b0b0b0'; // 未入湯（0回）
const SPRING_INACTIVE_COLOR = '#cccccc'; // 泉質不一致
const SPRING_STROKE_COLOR = '#7a3000';   // 名山の白ストロークと区別するための暗い縁

const visited = ['>', ['coalesce', ['get', 'count'], 0], 0];

/** 温泉レイヤーの paint を返す。filterType=null のときは全件同色。 */
function getSpringPaint(filterType) {
  // 入湯あり=オレンジ、未入湯=グレー（フィルタなし）
  // 入湯あり＋泉質一致=オレンジ、それ以外=グレー（フィルタあり）
  const typeMatch = filterType
    ? ['in', filterType, ['coalesce', ['get', 'spring_type'], ['literal', []]]]
    : null;

  const color = typeMatch
    ? ['case', ['all', visited, typeMatch], SPRING_ACTIVE_COLOR, SPRING_INACTIVE_COLOR]
    : ['case', visited, SPRING_ACTIVE_COLOR, SPRING_UNVISITED_COLOR];

  return {
    'circle-color': color,
    'circle-radius': [
      'interpolate', ['linear'], ['coalesce', ['get', 'count'], 0],
      0, 5,
      1, 8,
      3, 11,
      5, 14,
    ],
    'circle-stroke-width': 2,
    'circle-stroke-color': SPRING_STROKE_COLOR,
    'circle-opacity': 0.9,
  };
}

// 全ソース・レイヤーを初期スタイルに含めてまとめて登録
const sources = {};
const layers = [];

Object.entries(BASEMAPS).forEach(([key, config]) => {
  sources[key] = {
    type: 'raster',
    tiles: config.tiles,
    tileSize: config.tileSize,
    attribution: config.attribution,
    maxzoom: config.maxzoom,
  };
  layers.push({
    id: key,
    type: 'raster',
    source: key,
    layout: {
      visibility: key === DEFAULT_BASEMAP ? 'visible' : 'none',
    },
  });
});

// MapLibre GL JS の初期化
const map = new maplibregl.Map({
  container: 'map',
  style: {
    version: 8,
    sources,
    layers,
  },
  center: [139.767, 35.681], // 東京
  zoom: 10,
});

// ポップアップ（検索からも使えるようトップレベルで定義）
const popup = new maplibregl.Popup({
  closeButton: true,
  closeOnClick: false,
  maxWidth: '360px',
});

// コントロール追加
map.addControl(new maplibregl.NavigationControl(), 'top-left');
map.addControl(new maplibregl.ScaleControl({ unit: 'metric' }), 'bottom-left');
map.addControl(new maplibregl.FullscreenControl(), 'top-left');

// 地形 DEM ソースとスカイレイヤーをロード後に追加
const TERRAIN_SOURCE_ID = 'terrain-dem';

map.on('load', () => {
  map.addSource(TERRAIN_SOURCE_ID, {
    type: 'raster-dem',
    tiles: ['https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png'],
    tileSize: 256,
    encoding: 'terrarium',
    maxzoom: 12,
    attribution: '© <a href="https://registry.opendata.aws/terrain-tiles/">Mapzen, Amazon</a>',
  });

  // ヒルシェード（陰影）レイヤー：3D有効時に表示
  map.addLayer({
    id: 'hillshade',
    type: 'hillshade',
    source: TERRAIN_SOURCE_ID,
    layout: { visibility: 'none' },
    paint: {
      'hillshade-exaggeration': 0.5,
      'hillshade-shadow-color': '#473B24',
    },
  });

  // 名山 GeoJSON ソース + サークルレイヤー
  map.addSource('meizan', {
    type: 'geojson',
    data: '/meizan.geojson',
  });

  map.addLayer({
    id: 'meizan-circles',
    type: 'circle',
    source: 'meizan',
    layout: { visibility: 'visible' },
    paint: VIZ_MODES.category.paint,
  });

  // クリックでポップアップ表示
  map.on('click', 'meizan-circles', (e) => {
    const props = e.features[0].properties;
    const coords = e.features[0].geometry.coordinates.slice();

    const count = props.count ?? 0;

    let visitsHTML = '';
    if (count > 0 && props.visits) {
      const visits = typeof props.visits === 'string' ? JSON.parse(props.visits) : props.visits;
      const items = visits.map(v =>
        `<li>${v.date}${v.note ? `<span class="popup-visit-note">　${v.note}</span>` : ''}</li>`
      ).join('');
      visitsHTML = `
        <div class="popup-visits">
          <div class="popup-visits-label">登頂日</div>
          <ul class="popup-visits-list">${items}</ul>
        </div>`;
    }

    popup.setLngLat(coords).setHTML(`
      <div class="popup-content">
        <div class="popup-header">
          <span class="popup-icon">🏔</span>
          <div class="popup-title-block">
            <div class="popup-title">${props.name}</div>
            <div class="popup-yomi">${props.yomi}</div>
          </div>
        </div>
        <div class="popup-stats">
          <div class="popup-stat">
            <span class="popup-stat-label">標高</span>
            <span class="popup-stat-value">${props.elev_m.toLocaleString()} m</span>
          </div>
          <div class="popup-stat">
            <span class="popup-stat-label">登頂</span>
            <span class="popup-stat-value">${count} 回</span>
          </div>
        </div>
        ${visitsHTML}
      </div>
    `).addTo(map);
  });

  // ホバー時にカーソルをポインターに変更
  map.on('mouseenter', 'meizan-circles', () => {
    map.getCanvas().style.cursor = 'pointer';
  });
  map.on('mouseleave', 'meizan-circles', () => {
    map.getCanvas().style.cursor = '';
  });

  // 温泉 GeoJSON ソース + サークルレイヤー（名山の上に重ねる）
  map.addSource('springs', {
    type: 'geojson',
    data: '/springs.geojson',
  });

  map.addLayer({
    id: 'springs-circles',
    type: 'circle',
    source: 'springs',
    layout: { visibility: 'visible' },
    paint: getSpringPaint(null),
  });

  // 温泉クリックでポップアップ表示
  map.on('click', 'springs-circles', (e) => {
    const props = e.features[0].properties;
    const coords = e.features[0].geometry.coordinates.slice();

    const count = props.count ?? 0;
    const springTypes = props.spring_type
      ? (typeof props.spring_type === 'string' ? JSON.parse(props.spring_type) : props.spring_type)
      : null;

    let visitsHTML = '';
    if (count > 0 && props.visits) {
      const visits = typeof props.visits === 'string' ? JSON.parse(props.visits) : props.visits;
      const items = visits.map(v =>
        `<li>${v.date}${v.note ? `<span class="popup-visit-note">　${v.note}</span>` : ''}</li>`
      ).join('');
      visitsHTML = `
        <div class="popup-visits">
          <div class="popup-visits-label">入湯日</div>
          <ul class="popup-visits-list">${items}</ul>
        </div>`;
    }

    popup.setLngLat(coords).setHTML(`
      <div class="popup-content">
        <div class="popup-header">
          <span class="popup-icon">♨️</span>
          <div class="popup-title-block">
            <div class="popup-title">${props.name}</div>
            <div class="popup-yomi">${props.yomi}</div>
          </div>
        </div>
        <div class="popup-stats">
          <div class="popup-stat">
            <span class="popup-stat-label">入湯</span>
            <span class="popup-stat-value popup-stat-value--spring">${count} 回</span>
          </div>
          ${springTypes ? `
          <div class="popup-stat">
            <span class="popup-stat-label">泉質</span>
            <span class="popup-stat-value popup-stat-value--spring popup-spring-types">${springTypes.join(' / ')}</span>
          </div>` : ''}
        </div>
        ${visitsHTML}
      </div>
    `).addTo(map);
  });

  map.on('mouseenter', 'springs-circles', () => {
    map.getCanvas().style.cursor = 'pointer';
  });
  map.on('mouseleave', 'springs-circles', () => {
    map.getCanvas().style.cursor = '';
  });
});

// パネルセクションの折りたたみ
document.querySelectorAll('.panel-section-header').forEach(header => {
  header.addEventListener('click', () => {
    header.closest('.panel-section').classList.toggle('collapsed');
  });
});

// 背景地図切替ボタンを動的生成
let currentBasemap = DEFAULT_BASEMAP;

const buttonContainer = document.getElementById('layer-buttons');

Object.entries(BASEMAPS).forEach(([key, config]) => {
  const btn = document.createElement('button');
  btn.className = 'layer-btn' + (key === DEFAULT_BASEMAP ? ' active' : '');
  btn.dataset.key = key;
  btn.innerHTML = `<span class="icon">${config.icon}</span>${config.label}`;
  buttonContainer.appendChild(btn);

  btn.addEventListener('click', () => {
    if (key === currentBasemap) return;

    // 現在のレイヤーを非表示、選択レイヤーを表示
    map.setLayoutProperty(currentBasemap, 'visibility', 'none');
    map.setLayoutProperty(key, 'visibility', 'visible');
    currentBasemap = key;

    // ボタンのアクティブ状態を更新
    document.querySelectorAll('.layer-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
  });
});

// 3D地形切替ボタン
let is3D = false;

const viewButtonContainer = document.getElementById('view-buttons');
const btn3D = document.createElement('button');
btn3D.className = 'layer-btn';
btn3D.innerHTML = '<span class="icon">🏔️</span>3D地形';
viewButtonContainer.appendChild(btn3D);

btn3D.addEventListener('click', () => {
  is3D = !is3D;
  if (is3D) {
    map.setTerrain({ source: TERRAIN_SOURCE_ID, exaggeration: 1.5 });
    map.setLayoutProperty('hillshade', 'visibility', 'visible');
    map.easeTo({ pitch: 60, bearing: -20, duration: 800 });
    btn3D.classList.add('active');
  } else {
    map.setTerrain(null);
    map.setLayoutProperty('hillshade', 'visibility', 'none');
    map.easeTo({ pitch: 0, bearing: 0, duration: 800 });
    btn3D.classList.remove('active');
  }
});

// 傾きスライダー
const pitchControl = document.createElement('div');
pitchControl.className = 'camera-control';
pitchControl.innerHTML =
  '<div class="control-label"><span>傾き</span><span id="pitch-value">0°</span></div>' +
  '<input type="range" class="control-slider" id="pitch-slider" min="0" max="85" value="0" step="1">';
viewButtonContainer.appendChild(pitchControl);

const pitchSlider = document.getElementById('pitch-slider');
const pitchValueLabel = document.getElementById('pitch-value');

pitchSlider.addEventListener('input', () => {
  map.easeTo({ pitch: Number(pitchSlider.value), duration: 0 });
  pitchValueLabel.textContent = `${pitchSlider.value}°`;
});

// マップ操作（ドラッグなど）でpitchが変わった場合もスライダーに反映
map.on('pitchend', () => {
  const pitch = Math.round(map.getPitch());
  pitchSlider.value = pitch;
  pitchValueLabel.textContent = `${pitch}°`;
});

// 真上に戻すボタン
const resetViewBtn = document.createElement('button');
resetViewBtn.className = 'layer-btn';
resetViewBtn.innerHTML = '<span class="icon">⬆️</span>真上に戻す';
viewButtonContainer.appendChild(resetViewBtn);

resetViewBtn.addEventListener('click', () => {
  map.easeTo({ pitch: 0, bearing: 0, duration: 600 });
  pitchSlider.value = 0;
  pitchValueLabel.textContent = '0°';
});

// ─── 名山データ表示 UI ────────────────────────────────────────────────────────

let meizanVisible = true;
let currentViz = 'category';

const dataButtonContainer = document.getElementById('data-buttons');
const legendEl = document.getElementById('meizan-legend');

// 可視化モードごとの凡例 HTML を返す
function getLegendHTML(mode) {
  if (mode === 'category') {
    return `
      <div class="legend-title">種別</div>
      <div class="legend-row"><span class="legend-dot" style="background:#e74c3c"></span>百名山（No.1–100）</div>
      <div class="legend-row"><span class="legend-dot" style="background:#f39c12"></span>二百名山（No.101–200）</div>
      <div class="legend-row"><span class="legend-dot" style="background:#3498db"></span>三百名山（No.201–300）</div>
    `;
  }
  if (mode === 'elevation') {
    return `
      <div class="legend-title">標高</div>
      <div class="legend-gradient" style="background:linear-gradient(to right,#ffffcc,#feb24c,#f03b20,#800026)"></div>
      <div class="legend-label-row"><span>500 m</span><span>3800 m</span></div>
    `;
  }
  if (mode === 'count') {
    return `
      <div class="legend-title">登頂回数</div>
      <div class="legend-count-row">
        <div class="legend-count-item">
          <svg width="22" height="22"><circle cx="11" cy="11" r="5" fill="#cccccc" stroke="#fff" stroke-width="1.5"/></svg>
          <span>未登頂</span>
        </div>
        <div class="legend-count-item">
          <svg width="22" height="22"><circle cx="11" cy="11" r="8" fill="#3366ff" stroke="#fff" stroke-width="1.5"/></svg>
          <span>1回</span>
        </div>
        <div class="legend-count-item">
          <svg width="22" height="22"><circle cx="11" cy="11" r="11" fill="#3366ff" stroke="#fff" stroke-width="1.5"/></svg>
          <span>3回以上</span>
        </div>
      </div>
    `;
  }
  return '';
}

// 凡例の表示・非表示と内容を更新
function updateLegend(visible, mode) {
  legendEl.style.display = visible ? 'block' : 'none';
  if (visible) legendEl.innerHTML = getLegendHTML(mode);
}

// 名山レイヤー トグルボタン
const meizanToggleBtn = document.createElement('button');
meizanToggleBtn.className = 'layer-btn active';
meizanToggleBtn.innerHTML = '<span class="icon">⛰️</span>名山を表示';
dataButtonContainer.appendChild(meizanToggleBtn);

meizanToggleBtn.addEventListener('click', () => {
  meizanVisible = !meizanVisible;
  map.setLayoutProperty('meizan-circles', 'visibility', meizanVisible ? 'visible' : 'none');
  meizanToggleBtn.classList.toggle('active', meizanVisible);
  updateLegend(meizanVisible, currentViz);
});

// 可視化モード切替ボタン
const vizContainer = document.createElement('div');
vizContainer.className = 'viz-buttons';

Object.entries(VIZ_MODES).forEach(([key, cfg]) => {
  const btn = document.createElement('button');
  btn.className = 'viz-btn' + (key === currentViz ? ' active' : '');
  btn.textContent = cfg.label;
  btn.dataset.viz = key;
  vizContainer.appendChild(btn);

  btn.addEventListener('click', () => {
    if (key === currentViz) return;
    currentViz = key;

    // ペイントプロパティをまとめて更新
    Object.entries(VIZ_MODES[key].paint).forEach(([prop, val]) => {
      map.setPaintProperty('meizan-circles', prop, val);
    });

    // ボタンのアクティブ状態を更新
    vizContainer.querySelectorAll('.viz-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');

    // 凡例を更新
    updateLegend(meizanVisible, currentViz);
  });
});

dataButtonContainer.appendChild(vizContainer);

// 初期凡例を表示
updateLegend(meizanVisible, currentViz);

// ─── 温泉データ表示 UI ────────────────────────────────────────────────────────

let springsVisible = true;
let currentSpringFilter = null;

const springLegendEl = document.getElementById('spring-legend');

function getSpringLegendHTML(filterType) {
  const circle = (r, color) =>
    `<svg width="${r * 2 + 4}" height="${r * 2 + 4}"><circle cx="${r + 2}" cy="${r + 2}" r="${r}" fill="${color}" stroke="${SPRING_STROKE_COLOR}" stroke-width="2"/></svg>`;

  let html = `
    <div class="legend-title">♨️ 入湯回数</div>
    <div class="legend-count-row">
      <div class="legend-count-item">
        ${circle(5, SPRING_UNVISITED_COLOR)}
        <span>未入湯</span>
      </div>
      <div class="legend-count-item">
        ${circle(8, SPRING_ACTIVE_COLOR)}
        <span>1回</span>
      </div>
      <div class="legend-count-item">
        ${circle(11, SPRING_ACTIVE_COLOR)}
        <span>3回</span>
      </div>
      <div class="legend-count-item">
        ${circle(14, SPRING_ACTIVE_COLOR)}
        <span>5回以上</span>
      </div>
    </div>`;

  if (filterType) {
    html += `
      <div class="legend-spring-filter">
        <div class="legend-row">${circle(9, SPRING_ACTIVE_COLOR)}<span>${filterType}（入湯あり）</span></div>
        <div class="legend-row">${circle(9, SPRING_INACTIVE_COLOR)}<span>その他</span></div>
      </div>`;
  }
  return html;
}

function updateSpringLegend(visible, filterType) {
  springLegendEl.style.display = visible ? 'block' : 'none';
  if (visible) springLegendEl.innerHTML = getSpringLegendHTML(filterType);
}

// データパネルの仕切り線
const springDivider = document.createElement('div');
springDivider.className = 'data-divider';
dataButtonContainer.appendChild(springDivider);

// 温泉レイヤー トグルボタン
const springsToggleBtn = document.createElement('button');
springsToggleBtn.className = 'layer-btn active';
springsToggleBtn.innerHTML = '<span class="icon">♨️</span>温泉を表示';
dataButtonContainer.appendChild(springsToggleBtn);

springsToggleBtn.addEventListener('click', () => {
  springsVisible = !springsVisible;
  map.setLayoutProperty('springs-circles', 'visibility', springsVisible ? 'visible' : 'none');
  springsToggleBtn.classList.toggle('active', springsVisible);
  updateSpringLegend(springsVisible, currentSpringFilter);
});

// 泉質フィルタ セレクト
const springTypeSelect = document.createElement('select');
springTypeSelect.className = 'spring-type-select';

const defaultOption = document.createElement('option');
defaultOption.value = '';
defaultOption.textContent = '泉質でフィルタ（全て）';
springTypeSelect.appendChild(defaultOption);

SPRING_TYPES.forEach(type => {
  const opt = document.createElement('option');
  opt.value = type;
  opt.textContent = type;
  springTypeSelect.appendChild(opt);
});

dataButtonContainer.appendChild(springTypeSelect);

springTypeSelect.addEventListener('change', () => {
  currentSpringFilter = springTypeSelect.value || null;
  const paint = getSpringPaint(currentSpringFilter);
  Object.entries(paint).forEach(([prop, val]) => {
    map.setPaintProperty('springs-circles', prop, val);
  });
  updateSpringLegend(springsVisible, currentSpringFilter);
});

// 初期凡例を表示
updateSpringLegend(springsVisible, currentSpringFilter);

// ─── 検索機能 ──────────────────────────────────────────────────────────────────

const searchInput = document.getElementById('search-input');
const searchResultsEl = document.getElementById('search-results');
let searchTimer = null;
let latestResults = [];

searchInput.addEventListener('input', () => {
  clearTimeout(searchTimer);
  const q = searchInput.value.trim();
  if (!q) {
    closeSearchResults();
    return;
  }
  searchTimer = setTimeout(() => fetchSearch(q), 300);
});

searchInput.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') closeSearchResults();
});

document.addEventListener('click', (e) => {
  if (!e.target.closest('#search-box')) closeSearchResults();
});

function closeSearchResults() {
  searchResultsEl.style.display = 'none';
  searchResultsEl.innerHTML = '';
  latestResults = [];
}

async function fetchSearch(q) {
  try {
    const res = await fetch(`/search?q=${encodeURIComponent(q)}`);
    const data = await res.json();
    latestResults = data.results;
    renderSearchResults(data.results);
  } catch (_) {
    // ネットワークエラーは無視
  }
}

function renderSearchResults(results) {
  if (!results.length) {
    searchResultsEl.innerHTML = '<div class="search-no-results">見つかりませんでした</div>';
    searchResultsEl.style.display = 'block';
    return;
  }
  searchResultsEl.innerHTML = results.map((r, i) => {
    const icon = r.type === 'meizan' ? '⛰️' : '♨️';
    const sub = r.type === 'meizan'
      ? `${r.elev_m.toLocaleString()} m`
      : (r.spring_type ? r.spring_type.join(' / ') : '');
    return `<div class="search-result-item" data-index="${i}">
      <span>${icon}</span>
      <span class="search-result-name">${r.name}</span>
      <span class="search-result-yomi">${r.yomi}</span>
      ${sub ? `<span class="search-result-sub">${sub}</span>` : ''}
    </div>`;
  }).join('');
  searchResultsEl.style.display = 'block';

  searchResultsEl.querySelectorAll('.search-result-item').forEach(el => {
    el.addEventListener('click', () => {
      const r = latestResults[parseInt(el.dataset.index)];
      showSearchResult(r);
    });
  });
}

function showSearchResult(r) {
  searchInput.value = r.name;
  closeSearchResults();
  map.flyTo({ center: [r.lng, r.lat], zoom: 13, duration: 800 });

  const count = r.count ?? 0;
  let visitsHTML = '';
  if (count > 0 && r.visits) {
    const label = r.type === 'meizan' ? '登頂日' : '入湯日';
    const items = r.visits.map(v =>
      `<li>${v.date}${v.note ? `<span class="popup-visit-note">　${v.note}</span>` : ''}</li>`
    ).join('');
    visitsHTML = `
      <div class="popup-visits">
        <div class="popup-visits-label">${label}</div>
        <ul class="popup-visits-list">${items}</ul>
      </div>`;
  }

  if (r.type === 'meizan') {
    popup.setLngLat([r.lng, r.lat]).setHTML(`
      <div class="popup-content">
        <div class="popup-header">
          <span class="popup-icon">🏔</span>
          <div class="popup-title-block">
            <div class="popup-title">${r.name}</div>
            <div class="popup-yomi">${r.yomi}</div>
          </div>
        </div>
        <div class="popup-stats">
          <div class="popup-stat">
            <span class="popup-stat-label">標高</span>
            <span class="popup-stat-value">${r.elev_m.toLocaleString()} m</span>
          </div>
          <div class="popup-stat">
            <span class="popup-stat-label">登頂</span>
            <span class="popup-stat-value">${count} 回</span>
          </div>
        </div>
        ${visitsHTML}
      </div>
    `).addTo(map);
  } else {
    const springTypes = r.spring_type;
    popup.setLngLat([r.lng, r.lat]).setHTML(`
      <div class="popup-content">
        <div class="popup-header">
          <span class="popup-icon">♨️</span>
          <div class="popup-title-block">
            <div class="popup-title">${r.name}</div>
            <div class="popup-yomi">${r.yomi}</div>
          </div>
        </div>
        <div class="popup-stats">
          <div class="popup-stat">
            <span class="popup-stat-label">入湯</span>
            <span class="popup-stat-value popup-stat-value--spring">${count} 回</span>
          </div>
          ${springTypes ? `
          <div class="popup-stat">
            <span class="popup-stat-label">泉質</span>
            <span class="popup-stat-value popup-stat-value--spring popup-spring-types">${springTypes.join(' / ')}</span>
          </div>` : ''}
        </div>
        ${visitsHTML}
      </div>
    `).addTo(map);
  }
}
