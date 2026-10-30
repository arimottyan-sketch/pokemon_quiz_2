# 公式ポケモン説明文（旧ポケカ含む）追加リリース 2026-10-30

- ベース: POKEMON_QUIZ_OFFICIAL_QUALITY_REFINED_20261029.zip
- 公式カード個別ページで照合した新規登録: 5件（ヒヤップ、モグリュー、フシデ、バニプッチ、シビシラス）
- 既存の2023年カード説明文を年数による制限から復帰: 1件（バニリッチ）
- 従来のカード効果・大会情報は原則3年制限のまま。新たな旧カード説明文は `card_text_role=species_flavor` で明示的に管理。
- 新規カードの発売日について個別に検証していないので、`first_release_on` を捏造せず不要にした（ポケモン説明文に限定）。
- 既存の公式原文・URL: 811件は変更なし（ただし既存バニリッチ1件に新規の2種メタデータを付与し、問題表示テキストを公式原文に戻した）。新規登録後: 816件。
- 第1/第2ヒントで別々の原文を使う枠: 277/280。ひとつの原文を2段階表示する残り: 3枠 (ミネズミ, ヤナッキー, セゴール)。
- CSV: data/POKEMON_ALL280_HINTS_QUALITY_20261030.csv（第1・第2ヒントの出典原文と、アプリ上の表示用テキストを別列で記録）、data/POKEMON_CARD_FLAVOR_5_NEW_1_REENABLED_20261030.csv（追加・再有効化証跡）
- 改修ファイルは `quiz_engine.py`（カード説明文の時間制限例外に限定）、`tests/test_quality_oct29.py` および `tests/test_oct28_official_only.py`（旧8件ステージング固定テストのみ更新）、`tests/test_card_species_flavor_20261030.py`（追加）。UI の `app.py`、`progressive_quiz.py`、`theme.css` 等は一切変更しない。
- クイズ出題時には原文が長く、意味が一部重複する場合、`question_text` に出典文から完全一致する一文だけ使用し、`text` は原文を全文保存（バニプッチ、シビシラス）。

## 今回個別に確認した公式カード
- ヒヤップ（BW1-Bw 014/053）: https://www.pokemon-card.com/card-search/details.php/card/27169
- モグリュー（SI 229/414）: https://www.pokemon-card.com/card-search/details.php/card/40707
- フシデ（SM3H 022/051）: https://www.pokemon-card.com/card-search/details.php/card/33885
- バニプッチ（BKW 005/018）: https://www.pokemon-card.com/card-search/details.php/card/28394
- シビシラス（BKZ 008/018）: https://www.pokemon-card.com/card-search/details.php/card/27630
- バニリッチ（既存再有効化）: https://www.pokemon-card.com/card-search/details.php/card/44330

## 限界
- 今回の照合対象は列挙したカードだけ。既存の全レコードの公式原典を再検証したものではない。
- ミネズミ、ヤナッキー、セゴールは独立した別説明文を今回確認できず、ステージングを維持。
- 実ブラウザ上でのクリック・画像表示は検証していない。
