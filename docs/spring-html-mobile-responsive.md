# spring.html モバイル対応

**対象ファイル:** `spring.html`
**変更日:** 2026-03-30

---

## 背景と課題

スマートフォンでアクセスした際に以下の問題があった。

| 問題 | 原因 |
|------|------|
| サイドバーが画面幅の大半を占め、地図がほぼ見えない | サイドバーが `width: 340px` の固定幅で横並びレイアウト |
| ボタン・入力欄が小さくタップしにくい | デスクトップ向けのサイズ設計（高さ 30〜36px 程度） |
| テキスト入力時に iOS が画面をズームインする | `font-size` が 14px（iOS は 16px 未満で自動ズーム） |
| マーカータップ後にポップアップが閉じられない | ポップアップが `closeButton: false` のホバー前提設計 |

---

## 変更内容

### 1. レイアウト — 縦並びに切り替え

**デスクトップ（768px 以上）:** 変更なし（サイドバー左・地図右の横並び）

**モバイル（767px 以下）:**

```
┌─────────────────────────┐
│  サイドバー（上 50vh）   │  ← リスト表示
│  ▼ トグルボタン付き      │
├─────────────────────────┤
│  地図（残り高さ）         │
└─────────────────────────┘
```

- `body` を `flex-direction: column` に変更
- `#sidebar` の幅を `100%`、高さを最大 `50vh` に設定
- `#map` は `flex: 1` で残りの高さを占有（最低 `50vh`）

### 2. サイドバーの折りたたみ

ヘッダー右端に **▼/▲ トグルボタン** を追加。

| 状態 | 表示 |
|------|------|
| 展開（デフォルト） | サイドバー全体（最大 50vh）が表示 |
| 折りたたみ | ヘッダー行（48px）のみ表示、地図を広く使える |

フォームを開いた際はサイドバーが自動的に折りたたまれる。

### 3. フォームのフルスクリーンオーバーレイ化

モバイルでは `#form-panel` が `position: fixed; inset: 0` のフルスクリーンオーバーレイとして表示される。フォームを開いている間はサイドバーと地図の上に重なり、スクロールして全項目を入力できる。

### 4. ポップアップのタッチ対応

| デバイス | 動作 |
|----------|------|
| デスクトップ | マーカーにホバーで情報ポップアップ表示、カーソルを外すと閉じる（従来通り） |
| タッチデバイス | マーカーをタップするとポップアップ表示。**「✕」閉じるボタン**（44×44px）と **「編集」ボタン**（48px 高）を配置 |

タッチデバイスでは `mouseenter` / `mouseleave` イベントが動作しないため、hover 系のポップアップを無効化し click ベースに切り替えた。

### 5. タッチターゲットの拡大

Apple HIG・Material Design のガイドラインに合わせ、タップ可能な要素を最低 44px に統一。

| 要素 | 変更前 | 変更後 |
|------|--------|--------|
| 検索入力欄 | ~36px | 48px |
| リスト項目 | padding 10px | padding 14px |
| 「新規追加」ボタン | padding 10px | 48px |
| 保存・キャンセルボタン | ~38px | 52px |
| 削除・記録追加ボタン | ~32px | 48px |
| 入湯記録削除ボタン | ~28px | 44×44px |
| 泉質チェックボックス | padding 4px 10px | padding 9px 14px |

### 6. iOS 自動ズーム防止

iOS Safari はフォーカス時に `font-size: 16px` 未満の入力欄を自動ズームする。モバイルでは以下の要素すべてに `font-size: 16px` を適用した。

- `#search-input`
- `.form-input`
- `.form-select`
- `.visit-date`
- `.visit-note`

---

## CSS 設計

追加スタイルはすべて `@media (max-width: 767px)` ブロックにまとめ、デスクトップのスタイルには一切影響しない。

```css
@media (max-width: 767px) {
  body { flex-direction: column; }
  #sidebar { width: 100%; max-height: 50vh; /* ... */ }
  #sidebar.collapsed { max-height: 48px; }
  #map { flex: 1; min-height: 50vh; }
  /* ... */
  .maplibregl-popup-close-button {
    width: 44px !important;
    height: 44px !important;
  }
}
```

---

## JS 変更点

### タッチデバイス判定

```javascript
const isTouchDevice = window.matchMedia('(hover: none) and (pointer: coarse)').matches;
```

`pointer: coarse` はマウスではなく指・スタイラスを示す CSS4 メディア特性。UA スニッフィングより信頼性が高い。

### ポップアップの分岐

```javascript
const popup = new maplibregl.Popup({
  closeButton: isTouchDevice,  // タッチ時のみ閉じるボタンを表示
  closeOnClick: false,
  offset: 14,
});

if (!isTouchDevice) {
  // デスクトップ: hover ポップアップ
  map.on('mouseenter', 'springs-circle', ...);
  map.on('mouseleave', 'springs-circle', ...);
}

map.on('click', 'springs-circle', (e) => {
  if (isTouchDevice) {
    // タッチ: 情報ポップアップ + 編集ボタン
    popup.setHTML(`...`).addTo(map);
  } else {
    // デスクトップ: 直接フォームを開く
    openEditForm(s);
  }
});
```

### サイドバートグル

```javascript
document.getElementById('mobile-toggle').addEventListener('click', () => {
  const collapsed = sidebar.classList.toggle('collapsed');
  btn.textContent = collapsed ? '▲' : '▼';
});
```

---

## 動作確認ポイント

- [ ] iPhone Safari でサイドバーが縦並びになる
- [ ] トグルボタンでリストの折りたたみ・展開ができる
- [ ] 「新規追加」でフォームがフルスクリーン表示される
- [ ] テキスト入力時に画面がズームインしない
- [ ] マーカータップでポップアップが開き、✕ で閉じられる
- [ ] ポップアップの「編集」から編集フォームが開く
- [ ] デスクトップでの動作が従来と変わらない
