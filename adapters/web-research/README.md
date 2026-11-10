# Web research adapter for `research-first` and `final-audit`

Tool-specific steps for the neutral research method. The skills own the
procedure, the evidence order and the stop rules; this file only says how to
drive one local tool stack. No absolute paths: tools are found through the
host's MCP configuration or on `PATH`.

## Provider

A local search-and-fetch stack exposed as an MCP server named `web-stack`
(metasearch for discovery, a crawler that returns page text as Markdown).

| Step | MCP tool | Notes |
|---|---|---|
| discover candidate sources | `web_search` | read results as leads, never as evidence |
| read one primary source | `fetch_markdown` | the evidence step |
| read several known pages | `crawl_urls` | batches only |
| check the stack is up | `web_stack_status` | before blaming the source |
| broad multi-source pass | `web_research` | still read primary sources before concluding |

CLI fallback: `web-search` on `PATH` (`web-search --help`).

## Availability

- MCP server listed and `web_stack_status` healthy: use it.
- Server missing or unhealthy: use the CLI fallback if it is on `PATH`.
- Neither: say that current facts could not be checked; do not install or
  repair the stack (setup work, owner gate).

The binding itself (server registration and launcher location) is per-machine
configuration and is not part of this repository.
