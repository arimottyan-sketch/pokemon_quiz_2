# ポケモン情報クイズ：公式説明文の拡充（2026年10月30日）

## 実行結果

- 元データ: `POKEMON_QUIZ_CARD_LORE_ALL_YEARS_20261030.zip` の `data/official_quotes.json`、816件 / 対象280枠。
- **今回、公式カードの生態説明文を12件追加、既存のセゴール1件を再有効化**。全件合計**828件**。既存の原文816件は維持（セゴールのメタデータ・選考状態のみ更新）。
- 280枠すべて四択出題可能で、第1・第2ヒントに別の公式原文を用いる枠は**279/280枠**。
- **ヤナッキー（512）のみ**複数の公式カードが図鑑と同主題・同一文面であり、意味が重複しない別の公式生態記述を確認できなかった。同一の公式図鑑原文を前半・全文で開示する段階表示のまま。公式出典を捏造して「280/280独立」としない。
- `app.py`、`quiz_engine.py`、`progressive_quiz.py`、`theme.css`、`requirements.txt` は**元ZIPとバイト一致**。動作コードへの変更なし。
- 更新したのは `data/official_quotes.json`、追加レポートCSV、旧検査件数を前提としていた一部のテスト期待値、今回の新規回帰テスト。
- Python `unittest discover` による**49件の自動テスト成功**。ブラウザーでの実画面操作テストは未実施。

## 追加・再有効化した公式カード生態情報

| ID | ポケモン | 処理 | 追加する知識（原文の要旨でありCSVでは公式原文全文） | 公式個別ページ |
|---|---|---|---|---|
| 504 | ミネズミ | 追加 | 見張り当番でも背後から来る敵に気づかない | [BW7-B 060/070](https://www.pokemon-card.com/card-search/details.php/card/28283) |
| 519 | マメパト | 追加 | 命令を忘れて次の命令を待ってしまう | [BW6-Bf 050/059](https://www.pokemon-card.com/card-search/details.php/card/28144) |
| 522 | シママ | 追加 | 発光するたてがみで仲間と意思疎通 | [CS1p 005/009](https://www.pokemon-card.com/card-search/details.php/card/27005) |
| 527 | コロモリ | 追加 | ハート型の鼻の跡にまつわる言い伝え | [MG 005/016](https://www.pokemon-card.com/card-search/details.php/card/28780) |
| 528 | ココロモリ | 追加 | 求愛時の超音波は浴びると楽しい気分になる | [BW4-B 036/069](https://www.pokemon-card.com/card-search/details.php/card/27796) |
| 540 | クルミル | 追加 | 口から出す粘着糸で葉を縫い服を作る | [SM11 006/094](https://www.pokemon-card.com/card-search/details.php/card/36753) |
| 567 | アーケオス | 追加 | 仲間と協力して獲物を仕留める | [SV11W 130/086](https://www.pokemon-card.com/card-search/details.php/card/48042) |
| 577 | ユニラン | 追加 | 強いショックで体を包む液体が漏れる | [SV5K 030/071](https://www.pokemon-card.com/card-search/details.php/card/45176) |
| 600 | ギギアル | 追加 | ちびギアを飛ばし、戻らないと危険 | [BW4-B 054/069](https://www.pokemon-card.com/card-search/details.php/card/27814) |
| 610 | キバゴ | 追加 | 生え替わるたびキバが丈夫になる | [BW9-B 055/076](https://www.pokemon-card.com/card-search/details.php/card/28726) |
| 611 | オノンド | 追加 | 戦闘後に河原の岩でキバを磨く | [BW2-B 057/066](https://www.pokemon-card.com/card-search/details.php/card/27417) |
| 625 | キリキザン | 追加 | コマタナを率いて獲物を群れで追い詰める | [BW2-B 049/066](https://www.pokemon-card.com/card-search/details.php/card/27409) |
| 997 | セゴール | 再有効化 | 周囲の空気を凍らせて装備を形作る（装備自体は既存図鑑と重複） | [SV4a 234/190](https://www.pokemon-card.com/card-search/details.php/card/45020) |

## 出典と採用ルール

- 出典は**ポケモンカードゲーム公式**の個別カードページの「ポケモンの説明文」欄。ワザ・特性・対戦成績は追加に用いていない。発行年による除外なし。
- `data/POKEMON_CARD_FLAVOR_ENRICHMENT_20261030.csv` に公式原文、URL、採否・重複の評価、出題に使用した連続原文を収録。
- アプリが実際に読み込む一次データは `data/official_quotes.json`。全280枠のヒント原文・URL・出題表示文は `data/POKEMON_ALL280_HINTS_QUALITY_20261030_ENRICHED.csv`。
- 語尾の追加・作為的言い換えはなし。カード全文に既出知識を含む場合、選択した連続する原文1文のみ表示する例あり（アーケオス、ユニラン、オノンド、キリキザン）。
- **別々の原文=別々の話題、と保証するものではない**。特にセゴールは「氷のマスクと剣」が図鑑と重複するため「周囲の空気を凍らせる形成過程」を独立要素として評価した。異なる話題を1匹あたり2件以上保証するものでもない。

## 残る検証課題（誇張しない）

- 元からある816件の全件について、今回一つずつ出典URLを再訪問して照合したわけではない。今回の12件と再有効化1件は個別公式ページで確認した。
- ヤナッキーでクイズに適した独立の公式生態事実を確保できていない。
- 選択肢の4件重複排除など自動テストは成功したが、ユーザー操作・実ブラウザー表示の確認は実施していない。
- `README_CARD_LORE_20261030.md` など2026年10月30日までの旧READMEは**当時の記録**で、277/280など古い数字が含まれる。最新情報は本READMEと `POKEMON_ALL280_HINTS_QUALITY_20261030_ENRICHED.csv` が優先する。
