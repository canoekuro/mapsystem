# Project Guidelines (SSoT)

このファイルはプロジェクト固有のガイドラインを記述する場所です。
技術的な決定事項、アーキテクチャ、コマンドなどをここに追記してください。

## 参照先
- **行動規範:** `.agents/rules/` を参照してください。
- **ワークフロー:** `.agents/workflows/` を参照してください。
- **スキル:** `.agents/skills/` を参照してください。
- **プロジェクト概要:** `SPEC.md` を参照してください。

## Claude Code ネイティブ機能（PDCA + サブエージェント委譲）
- **PDCA ワークフロー:** `/pdca`（`.claude/commands/pdca.md`）。レビュー→計画→改修→コミットの
  改善サイクルを、メインセッションがオーケストレーションしながら回す。
- **実装サブエージェント:** `.claude/agents/` 配下。トークン節約のため実装を委譲する。
  - `implementer-sonnet`（Sonnet）: ルーチン・標準実装。
  - `implementer-opus`（Opus）: 難易度の高い実装。
  - 最難所はメインセッション（Fable 5 / Opus）が直接実装する。
- **役割分担の規範:** `.agents/rules/agent-orchestration.md`（常時ON）。メインは設計・監査・
  レビューに専念し、実装は上記サブエージェントへ委譲、成果は監査後にコミットする。