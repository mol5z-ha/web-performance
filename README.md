# web-performance

Webサイト・Webアプリの待ち時間を、実測から改善する日本語のCodexスキル。

特定のサービスへの課金や技術の採用を先に決めず、配信・API・DB・画像・画面処理・キャッシュ・起動待ちを切り分けます。「高速化の仕組みがある」と「今回速くなった原因が分かった」を区別します。

## 使う場面

- 最初の表示、検索、ページ移動、保存が遅い。
- 課金していないのに速くなった理由を知りたい。
- サーバー増強が必要か、コード改善で足りるか判断したい。
- キャッシュや先読みを導入し、更新反映とアクセス権も保ちたい。

原因の質問では調査・説明、改善の依頼では実装・検証まで進めます。SEO全般やデザインだけの依頼を速度監査に広げません。

## インストール

Pythonの補助ツール以外はMarkdownだけで利用できます。Codexでは、このリポジトリをスキルフォルダーに配置します。非公開リポジトリの取得にはアクセス権とGitHub認証が必要です。

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

## HTTP測定ツール

Python 3.10以上、追加依存なし。副作用のない公開URLだけを対象にしてください。

```sh
python scripts/http_probe.py https://example.com/ --count 3
python -m unittest discover -s tests -v
```

URLや本文は結果に含めず、ステータス、取得時間、バイト数、一部キャッシュヘッダーをJSONで返します。リダイレクトは追従しません。完全取得した2xxのみを集計し、それ以外があれば終了コード1です。

これはブラウザ計測・負荷試験ではありません。TTFB、LCP、実利用のp95を測ったと解釈しないでください。認証や書き込み操作の速度は、対象プロジェクトの適切な計測で確認します。

## 検証の範囲

GitHub ActionsでPython 3.10 / 3.13の補助ツールテスト、スキルのメタデータ・参照リンク検査を実行します。テストはローカルHTTPサーバーのみを使います。手動評価ケースはAIの判断を点検するための資料で、自動評価済みという意味ではありません。

各サービスの料金、無料枠、休止条件や推奨設定は固定値にせず、適用時に公式情報を確認する設計です。案件固有のURL・顧客情報・認証情報は含めていません。
