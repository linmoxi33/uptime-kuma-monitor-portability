# uptime-kuma-monitor-portability

Can a `GET /api/monitors` payload rebuild your monitors? **No.** This CLI audits a saved API response and prints exactly which behaviour-bearing fields are missing — per monitor, with a one-minimal witness.

Uptime Kuma's v3 API is read-only today, so the API export is the only programmatic way out. Before you plan a migration, backup or bulk edit, you need to know whether that export is enough. It is not: this tool turns "probably incomplete" into a field list you can act on.

Upstream: https://github.com/louislam/uptime-kuma

## What upstream does, and what it lacks

Uptime Kuma's alpha `API and MCP` surface (PR #8072, merged Oct 2026) exposes `GET /api/info` and `GET /api/monitors`. The OpenAPI `Monitor` schema for the latter declares **11 fields**
([`server/routers/api-router.js#L185-L197`](https://github.com/louislam/uptime-kuma/blob/master/server/routers/api-router.js#L185-L197), audited at `4f6661cfa83a06be0353d5536ef3d9ee0064f534`):

`id, name, type, active, parent, childrenIDs, tags, path, pathName, interval, weight`.

The server record that `Monitor.toJSON()` emits has **86 fields** — `url`, `method`, `accepted_statuscodes`, `hostname`, `port`, `keyword`, `jsonPath`, `expectedValue`, `retries`, `timeout`, and so on
([`server/model/monitor.js#L133-L220`](https://github.com/louislam/uptime-kuma/blob/master/server/model/monitor.js#L133-L220)).

Write support is the long-standing gap: [issue #118](https://github.com/louislam/uptime-kuma/issues/118) ("retrieve, update, remove or add monitors via API calls") has been open since 2021 with **786 reactions**; the MCP bridge only forwards parameterless GET routes
([`server/routers/mcp-router.ts`](https://github.com/louislam/uptime-kuma/blob/master/server/routers/mcp-router.ts)). The project wiki also states the internal API is "not officially supported for third-party integrations".

So: **it can list monitors, but nobody can recreate one from what it lists** — 9 of the 11 API fields come from the record, the rest of the 86 do not.

## What this tool does / does not do

Does:
- validates a saved `GET /api/monitors` body against the declared API schema (type errors are reported per field);
- checks every monitor against the fields its type needs to be recreated (`http`, `keyword`, `json-query`, `port`, `ping`, `dns`, `docker`, `mqtt`, `grpc`, `steam`, `real-browser`, `push`, `group`);
- emits a one-minimal witness — each listed field alone already blocks a rebuild;
- `--emit-template` writes a fill-in JSON with the missing fields set to `null`;
- deterministic, offline, zero dependencies (Python 3.8+ stdlib).

Does not:
- call any Uptime Kuma instance, create monitors, or write to a database;
- claim that a monitor *works* after you fill the template — that still needs the missing write API ([#118](https://github.com/louislam/uptime-kuma/issues/118));
- model notification bindings, tags or API keys.

## Install

```bash
git clone <this repo> && cd uptime-kuma-monitor-portability
python3 bin/uptime-kuma-monitor-portability audit --input examples/in/api-monitors.json
```

No install step, no dependencies.

## Usage

```bash
# human-readable audit (exit 1 because the example payload cannot rebuild anything)
python3 bin/uptime-kuma-monitor-portability audit --input examples/in/api-monitors.json

# machine-readable report
python3 bin/uptime-kuma-monitor-portability audit --input examples/in/api-monitors.json --json

# also write the fill-in template
python3 bin/uptime-kuma-monitor-portability audit --input examples/in/api-monitors.json \
  --json --emit-template /tmp/template.json
```

Real output on `examples/in/api-monitors.json` (committed as `examples/out/report.json`):

```text
monitors=3 recreatable=0 not_recreatable=3 errors=3
error   E_NOT_PORTABLE   cannot rebuild monitor 'blog' (http) from the API payload: missing 4 behaviour-bearing field(s): accepted_statuscodes, maxredirects, method, url
error   E_NOT_PORTABLE   cannot rebuild monitor 'landing-keyword' (keyword) from the API payload: missing 3 behaviour-bearing field(s): keyword, method, url
error   E_NOT_PORTABLE   cannot rebuild monitor 'db-port' (port) from the API payload: missing 2 behaviour-bearing field(s): hostname, port
```

`--json` shape: `summary` (`monitors`, `recreatable`, `not_recreatable`, `api_fields`, `model_fields`, `required_fields_checked`, `errors`), `coverage` (per API field, how many monitors carry it), `monitors[]` (`recreatable`, `missing`, `witness`), `findings[]`.

### Exit codes

| code | meaning |
| --- | --- |
| 0 | payload is structurally valid and every monitor is recreatable (or the list is empty) |
| 1 | findings: a monitor is not recreatable, or the payload violates the API schema |
| 2 | usage or input error (unreadable file, invalid JSON, missing `monitors`) |

## Tests

```bash
python3 -m unittest discover -s tests -v
```

13 tests, all behavioural (input → JSON/exit code), including every exit-code path and a one-minimality assertion. Last run: `Ran 13 tests ... OK`.

## 本轮创新

B 级：首次把 Uptime Kuma 只读 API 的「可移植性」量化成一个可复算的结论 —— 文档 schema 的 11 个字段对上 `Monitor.toJSON()` 的 86 个字段，9 个来自记录、其余 77 个不在 API 里，并给出 per-monitor 的 one-minimal 缺失见证。此前只有 issue #118 的「想要写 API」诉求，没有任何人给出「读 API 的载荷够不够重建监控器」的字段级答案。这个结论不依赖某个热榜项目：它测的是 API schema 与运行时记录之间的契约落差。

## 局限

- `examples/in/*.json` 是**按上游 OpenAPI schema 手写的离线 fixture**，不是从真实实例抓取的响应；本轮没有运行 Uptime Kuma（环境不允许 `npm install`）。字段目录钉在 commit `4f6661cf`，上游改 schema 后需要重新取证。
- 类型检查只覆盖 API schema 的 11 个字段与重建所需字段的**存在性**，不校验 `accepted_statuscodes` 的取值合法性、条件表达式语法等语义。
- `push` 类型的重建不需要额外字段，但仍缺 `token` 之类运行时凭据（API 从不返回 secrets），所以「recreatable」只表示字段齐全，不代表凭据齐全。

## License

MIT.
