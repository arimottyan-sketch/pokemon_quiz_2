# ポケモン情報クイズ：2026年10月30日最終更新版

起動: `pip install -r requirements.txt` → `streamlit run app.py`。

## 今回の更新
- ヤナッキーのだんだんヒントを **①公式図鑑（気性・尻尾・苦い葉っぱ）→②BW2ゲーム公式のジムリーダー3兄弟エピソード→③特性→④タイプ→⑤シルエット** とした。
- BW2の公式ページに載る原文は改変せず `data/official_quotes.json` 内 `text` に保持。クイズ表示用 `question_text` はBWおよびBW2公式ページ、公式ポケモン図鑑に基づく編集文。旧作の個体と続編の個体が同一かどうかは断定していない。
- 特性情報の例外出典に限り、ユーザー許可によって「ポケモン徹底攻略」を参照。隠れ特性 `しんりょく` と、公式図鑑掲載の通常特性 `くいしんぼう` を区別して表示。例外出典を「公式」と誤表記しない。
- 280枠全てが独立した2つの**別原文**を用いた段階ヒントを持つ（ただし内容がすべて独立した知識であることまでは主張しない）。元の828件にBW2の公式情報1件を追加して829件。
- `quiz_engine.py`, `theme.css`, `requirements.txt` は前回ZIPから変更なし。`progressive_quiz.py` はヤナッキー用のヒント順序と許可済み特性出典のみ変更。`app.py` は許可済み特性出典の正しい表示と、旧ZIPで欠けていたプロフィール取得用3関数の復旧のみ変更。
- テストと詳細は `README_FINAL_20261030.md`。過去の `README_QUALITY_*` や `README_OFFICIAL_ENRICHMENT_*` は更新前のスナップショット。

## 主な出典
- 『BW2』公式： https://www.pokemon.co.jp/ex/b2w2/koryaku/koryaku08.html
- 『BW』公式： https://www.pokemon.co.jp/series/bw/characters/characters07.html
- ポケモン図鑑： https://zukan.pokemon.co.jp/detail/0512
- 『BW2』おもいでリンク： https://www.pokemon.co.jp/ex/b2w2/system/system07.html
- 隠れ特性に限る特例： https://yakkun.com/ch/zukan/search/?ch=0&egg=0&final_evo=1&group_n%5B%5D=5&group_n%5B%5D=6&machine=0&move=164&page=100&present=0&search=1&tutors=0

## 検証上の限界
- 当初の828件すべてを今回の調査で再訪問したわけではない。
- BWではデントが実際に使ったヤナップがBW2で同一個体のまま進化した、と断定するものではない。
- アニメのヤナッキー関連記述は既存データに記録として保持するが、`quiz_enabled: false` のままで出題しない。
- 実ブラウザーの画面操作は自動テストと異なるため、動作保証には含めない。
