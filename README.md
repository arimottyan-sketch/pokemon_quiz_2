# ずかんノート — ポケモン生態クイズ

ゲーム内ポケモン図鑑の**公式原文**を最優先にした、独立したStreamlit四択クイズです。以前のポケモン名前当てアプリとは無関係に動きます。

> **収録状況（2026年10月21日）**：イッシュ156匹＋パルデア120匹＝276匹が対象です。今回の初期ファイルには15匹のエントリーがあり、そのうち公式ページの検索結果で本文と作品名を照合できた12匹だけが体験モードの出題対象です（イッシュ8匹、パルデア4匹）。残る3匹は旧データの未再照合扱いで出題しません。全276匹分の実取得はGitHub Actionsで**まだ実施していません**。

## 何ができる？

- 図鑑の説明文 → そのポケモンの名前を4択で当てる
- 名前／公式アートワーク → 正しい図鑑の説明文を4択で当てる
- 両方向のミックス、問題数の選択、スコア、間違いの復習
- 答え合わせ後、**ゲーム作品名・原文・公式図鑑URL**を表示。誤答選択肢の出典も展開可能
- 公式ゲームサイト／アニメ公式X／ポケカ公式の情報は**回答後の補足専用**
- ポケカのカード効果や公式大会は直近3年のみ、ゲーム内図鑑原文は古い作品も使用
- 公式本文にポケモン名が含まれる場合は、伏せ字や要約をせず逆向きの問題に変更
- 未収録の図鑑番号を確認可能。全種モードは全種が揃うまで開始不可

## ファイル構成

```text
app.py                      アプリ本体（読み取り専用、起動中の収集なし）
quiz_core.py                出題・正誤判定・品質チェックのロジック
collect_official.py         GitHub Actionsで一括収集するためのスクリプト
requirements.txt            Python依存ライブラリ
.streamlit/config.toml      Streamlitの配色とフォント設定
.github/workflows/collect-pokedex.yml  手動で原文を収集してコミット
 data/pokedex.json          公式図鑑テキストと作品名、照合状況（アプリはこれを読む）
 data/supplements.json      公式HP・アニメ公式X・最近のポケカ公式の補足
 data/collection_status.json  収集結果と失敗した図鑑番号
tests/                      テストコード
```

## GitHubへ配置する（新規プロジェクト）

1. GitHubで新規リポジトリを作成（例：`pokedex-lore-quiz`）。
2. このZIPを展開する。GitHub Desktopを利用する場合、展開した**中身**をリポジトリ直下へコピー → Commit → Push。
3. GitHub画面だけで作る場合は `Add file` → `Upload files` でルートの `.py` と `requirements.txt` を登録し、フォルダ配下の `data/`、`.streamlit/`、`.github/workflows/` のパスとファイルも同じように作成。GitHub上で `app.py` と `data/pokedex.json` が**同じリポジトリにあり、正しいパス**で置かれていることを確認してください。
4. **Actions** タブ → 左側の **「公式図鑑の収集と固定保存」** → **Run workflow** → Branch `main` → 実行。
5. ワークフロー終了後、`data/collection_status.json` の `fetched_from_official_count` を確認。目標は **276**。`missing_ids` が空でなければ再実行して未取得を試行します。
6. `git push` に書き込み権限の403エラーが出た場合はリポジトリの `Settings` → `Actions` → `General` → `Workflow permissions` を確認してください。GitHubや組織の権限制限によりコミットが拒否されることがあります。

**注意**：Actionsによる公式サイトへの実通信・全件保存の動作は、この環境ではまだ確認できていません。公式側のHTML構造が変更されていたりアクセスを拒否した場合は、未取得番号とエラーが報告されます。取得できない原文を捏造したり、一部を除いた「全種完成版」に見せることはありません。収集ワークフローは**手動起動のみ**で、起動したStreamlitアプリは公式サイトへアクセスしません（画像の読み込みは別）。

## Streamlit Community Cloudで公開

1. https://share.streamlit.io/ にアクセスし、GitHubアカウントと連携。
2. **Create app** → **Yup, I have an app** を選択。
3. 新規リポジトリ、branch `main`、**Main file path: `app.py`** を指定して Deploy。
4. データ収集が途中でもアプリの体験モードは利用可能。276匹揃ったら全種モードが有効になります。以後はGitHubのJSONを更新するだけでサイトにも反映されます。

参考：
- https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy
- https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax

## ローカルで実行・テストする

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
streamlit run app.py
```

図鑑の一括取得は **GitHub Actions** から実行することを推奨します。ローカルの場合：

```bash
python collect_official.py
```

このコマンドは**実際に**公式サイトへアクセスし、成功したデータだけを更新します。未取得があれば終了コード2になります。`--refresh-all` は保存済みを再取得します。元原文、作品名、公式ページURL、原文SHA256も保存します。SHA256は保存後の変化検知であり、公式サイトの真偽や内容の意味まで保証するものではありません。

## 出典・原文に関する運用規約

1. 図鑑説明文は**ゲーム内の原文と作品名の組**で管理し、改変・要約しない。作品表示の末尾部分だけ本文とは別フィールドに分けて表示する。
2. `data_status=official_html_collected`（公式HTMLから抽出）または `official_index_excerpt_reviewed`（公式検索結果から原文を照合）のものだけ出題する。前版の未再照合データは出題しない。
3. 図鑑の出典は `https://zukan.pokemon.co.jp/detail/XXXX` の一致した番号だけ採用する。本文に自分の名前があっても削除しない。
4. 図鑑以外の紹介文は `data/supplements.json` に記録する。公式Xは公式発表でアカウントの所有者を示した裏付けも必要。X投稿本文の直接照合が不可能なものは追加しない。
5. ポケカはカード発売日または大会日を記録し、閲覧時点から3年を超えたものは表示しない。過去大会の強さを「現環境でも強い」と断定しない。
6. ポケモン公式とは無関係のファン制作サイトです。公式のコンテンツ・画像・原文の権利は各権利者に属します。公開・配布の際は原文や画像の利用条件に留意してください。
