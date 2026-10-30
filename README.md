# web-performance

Webサイト・Webアプリの待ち時間を、実測から改善する日本語のCodexスキル。

特定のサービスへの課金や技術の採用を先に決めず、配信・API・DB・画像・画面処理・キャッシュ・起動待ちを切り分けます。「高速化の仕組みがある」と「今回速くなった原因が分かった」を区別します。

## 使う場面

- 最初の表示、検索、ページ移動、保存が遅い。
- 課金していないのに速くなった理由を知りたい。
- サーバー増強が必要か、コード改善で足りるか判断したい。
- キャッシュや先読みを導入し、更新反映とアクセス権も保ちたい。

原因の質問では調査・説明、改善の依頼では実装・検証まで進めます。SEO全般やデザインだけの依頼を速度監査に広げません。

## このリポジトリを読ませると増えるもの

- ソースしかない段階でも、呼出経路から件数依存・要求の直列化・過剰取得を追い、次の測定箇所まで絞る診断手順。
- 操作全体の支配区間と対策の効果上限を考え、目標に届かない部分最適化を見分ける判断。
- 期待本文と照合したHTTP測定、失敗や条件違いを含む前後比較を拒否する実行ツール。

単独でブラウザやサーバーに接続する機能はありません。使用するAIにプロジェクトのソース・必要な実行権限を与えてください。公開リポジトリを読めるAIには、SKILL.mdと必要な参照資料を読み、下記の課題に適用するよう依頼できます。

```text
このリポジトリのSKILL.mdを適用して、検索ボタンを押してから正しい結果が
表示されるまでの待ち時間を改善してください。現状を再現して原因を絞り、
必要な修正、結果の正しさの確認、同条件の前後比較まで実施してください。
```

## インストール

Pythonの補助ツール以外はMarkdownだけで利用できます。Codexでは、この公開リポジトリをスキルフォルダーに配置します。取得にGitHubへのログインは不要です。

macOS / Linux（既存フォルダーがない場合）:

```sh
git clone https://github.com/mol5z-ha/web-performance.git "${CODEX_HOME:-$HOME/.codex}/skills/web-performance"
```

Windows PowerShell:

```powershell
$skillsBase = if ($env:CODEX_HOME) { Join-Path $env:CODEX_HOME 'skills' } else { Join-Path $env:USERPROFILE '.codex/skills' }
git clone https://github.com/mol5z-ha/web-performance.git (Join-Path $skillsBase 'web-performance')
```

新しいチャットで呼び出します。

```text
$web-performance このプロジェクトの検索が遅い原因を調べ、必要な改善と前後比較まで進めてください。
```

調査のみの場合:

```text
$web-performance 最近速くなった理由を調べてください。設定変更やデプロイは不要です。
```

他のエージェントでも、[SKILL.md](SKILL.md)を入口に必要な参照資料を読ませて使えます。UIメタデータはCodex用です。

## 内容

| ファイル | 用途 |
| --- | --- |
| [SKILL.md](SKILL.md) | 適用範囲、進め方、完了基準 |
| [measurement.md](references/measurement.md) | 比較条件、測定の限界 |
| [interventions.md](references/interventions.md) | 症状と対策の判断表 |
| [cache-and-lifecycle.md](references/cache-and-lifecycle.md) | 鮮度、権限、先読み、定期通信 |
| [validation-cases.md](references/validation-cases.md) | 判断品質の手動評価ケース |
| [http_probe.py](scripts/http_probe.py) | 公開URLへの小規模・逐次HTTP測定 |
| [diagnosis.md](references/diagnosis.md) | 次の観測、ソースのみの診断、効果上限、変更の採否 |
| [compare_http.py](scripts/compare_http.py) | 正しい同一本文・申告条件を持つ前後レポートの比較 |
| [demo_index.py](scripts/demo_index.py) | ローカルSQLite索引の再現実験。実行計画・期待結果・生標本を出力 |
| [timeline_budget.py](scripts/timeline_budget.py) | 観測した依存図から終了時間・理論下限・目標を満たす時間予算を計算 |

## HTTP測定ツール

Python 3.10以上、追加依存なし。副作用のない公開URLだけを対象にしてください。

```sh
python scripts/http_probe.py https://example.com/ --count 3
python -m unittest discover -s tests -v
```

URLや本文は結果に含めず、ステータス、取得時間、バイト数、一部キャッシュヘッダーをJSONで返します。リダイレクトは追従しません。完全取得した2xxのみを集計し、それ以外があれば終了コード1です。

これはブラウザ計測・負荷試験ではありません。TTFB、LCP、実利用のp95を測ったと解釈しないでください。認証や書き込み操作の速度は、対象プロジェクトの適切な計測で確認します。

`--expect-sha256` を指定すると仕様・fixtureと照合済みの期待本文を検証し、速い200でも内容不一致なら終了コード1にします。`--condition` と `--revision` を含めて保存した前後レポートを比較できます。使い方と条件は[測定手順](references/measurement.md#正しい本文を保つ前後比較)にあります。

```sh
python scripts/compare_http.py before.json after.json
python scripts/demo_index.py
python scripts/timeline_budget.py examples/timeline.json
```

比較ツールは未確認の本文、失敗標本、条件不一致を含むと変化率を出しません。同じ条件ラベルが実際の環境一致を保証するわけではなく、操作者による確認が必要です。

2026-10-30のWindows / Python 3.11のローカル索引実験では、期待した20件の結果を全14標本で保持し、SQLiteの計画はSCANからINDEX SEARCHへ変わりました。[初回の生標本](evaluation/index-http-run.json)ではHTTP中央値15.37ms→15.94ms（+3.71%）で範囲も重なりました。[DB区間も測った再実験](evaluation/index-db-run.json)ではSQL実行・取得の中央値0.6941ms→0.2732ms、HTTP全体2.36ms→14.91msでした。データ量を変えて良い数字を選ばず、両結果を残しています。

SQL区間の短縮は観測しましたが、HTTP高速化は確認できません。次に操作全体の支配区間を調べる判断になります。固定順序やOSのスケジューリング・キャッシュの影響も残っています。このデモはツールの動作確認であり、スキル有無のAI性能比較ではありません。

保存した2回の生標本は比較結果の `performance_conclusion` 追加前の出力です。履歴を加工せず保持しています。現行版は範囲の重なりがあれば `inconclusive` とし、変化率を記述統計として返します。このルールは有意差検定ではなく、重ならない場合も因果関係を証明しません。上記のOS・キャッシュ等は影響候補で、今回の原因を特定したものではありません。

## 検証の範囲

2026-10-30のClaude比較では、通常指示も主要な原因候補を正しく選べました。改訂版は時間予算を具体化しましたが、未根拠の因果・数値断定も残りました。[失敗・退行を含む比較結果と実入力](evaluation/final-summary.md)を残しています。各条件1回の合成課題であり、AIの一般的な性能向上は実証していません。

この結果を受け、時間予算を計算する `timeline_budget.py` を追加しました。JSON例とテストで計算を確認しており、AIに使わせた場合の実案件の成果向上は別途評価が必要です。測定ツールの正しさとAIの判断品質を同じ合格として扱いません。

GitHub ActionsでPython 3.10 / 3.13の補助ツールテスト、スキルのメタデータ・参照リンク検査を実行します。テストはローカルHTTPサーバーのみを使います。手動評価ケースはAIの判断を点検するための資料で、自動評価済みという意味ではありません。

各サービスの料金、無料枠、休止条件や推奨設定は固定値にせず、適用時に公式情報を確認する設計です。案件固有のURL・顧客情報・認証情報は含めていません。

## ライセンス

[MIT License](LICENSE)。商用・個人のプロジェクトで利用、変更、再配布できます。ライセンスの条件に従い、著作権表示と許諾表示を保持してください。
