# Changelog

All notable changes to log4p are documented here. This project follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `SyslogLayout` (RFC 3164) and `RFC5424Layout` render complete, `<PRI>`-framed
  syslog lines and can attach to any appender; `SyslogAppender` now uses them.
- `PatternLayout` gains `alwaysWriteExceptions` (default `True`) plus optional
  `header` / `footer` strings written by stream appenders.
- `%map{key}` pattern converter reads `MapMessage` fields, and `%enc` is an
  alias for `%encode`.
- `JSONLayout` gains `includeThreadContext`, `includeTimeMillis`,
  `stacktraceAsString`, and `propertiesAsList` options.
- `CallableFilter` matches on an arbitrary Python predicate (log4j2
  `ScriptFilter` analogue).
- `MarkerPatternSelector` lets a `PatternLayout` switch patterns based on the
  record's marker (with marker-hierarchy matching and a default).
- `MapFilter` matches `MapMessage` events by key/value pairs (`and`/`or`).
- `fileConfig(..., monitorInterval=N)` watches a config file and re-applies it
  when it changes (log4j2's `monitorInterval`).
- Pattern lookups `${date:format}` (current time) and `${lower:...}` /
  `${upper:...}` (case-shifting, with nested lookups), plus `${sd:key}` /
  `${map:key}` message-field lookups and `:-default` fallbacks for `sys`.
- `CronRollingFileAppender` rolls on a cron schedule, backed by the exported
  `CronExpression` parser (five- or six-field expressions with lists, ranges,
  steps, and month/day names).
- `TimeFilter` matches records by time-of-day (with midnight-wrapping windows).
- `StructuredDataFilter` matches `StructuredDataMessage` events by
  structured-data type and key/value pairs (`and`/`or`).
- `MemoryAppender` captures rendered events and records in memory (with an
  optional `maxSize` ring limit) for tests and assertions.
- `ConsoleAppender` gains an `immediateFlush` option (default `True`).

### Changed

- Added thread-safety stress tests, deterministic fuzz tests, and a
  `benchmarks/benchmark.py` throughput harness.

## [0.2.0] - 2026-10-11

### Added

- `$${...}` escaping renders a literal `${...}` in patterns and config values.
- `HttpAppender` POSTs (or GETs) each event to an HTTP endpoint, defaulting to
  a JSON body with optional headers and TLS verification toggle.
- `FailoverAppender` tries a primary appender and falls back through a list of
  failover appenders on error.
- `AsyncAppender` log4j2 options: `bufferSize`, `blocking`, and
  `discardingThreshold` (drop sub-`WARN` events when the queue is nearly full).
- `NoMarkerFilter` (records without a marker) and `BurstFilter` (token-bucket
  rate limiting with a level bypass).
- `JSONLayout` options: `compact`, `includeStacktrace`, `includeLocation`,
  `eventEol`, and static `properties`.
- `filters` on `root` and named `loggers` in dict/YAML config.
- Structured messages: `MapMessage`, `StringMapMessage`, and
  `StructuredDataMessage`. Their key/value data is flattened into top-level
  fields by `JSONLayout`/`LogfmtLayout`, and `%m` renders `key="value"` pairs.
- MDC/NDC parity helpers: `MDC.putAll`/`setContext`/`containsKey`/`isEmpty`/
  `getContext`/`getImmutableContext`, `NDC.remove`/`getStack`/`isEmpty`;
  `Logger.isEnabled(level)` and `LoggerManager.exists(name)`.
- Per-event lookups in `PatternLayout`: `${ctx:key}` (with defaults),
  `${env:NAME}`, `${sys:attr}`, and `${marker}`.
- `RoutingAppender` routes each event to a child appender selected by a context
  value (with an optional default route).
- `ContextMapFilter` (MDC/context key-value matching, `and`/`or`) and
  `DynamicThresholdFilter` (per-context-value threshold).
- Custom levels in config via a top-level `levels:` map.
- Optional timezone in `%d{format}{timezone}` (`UTC`, `GMT+2`, `+05:30`, or any
  IANA name via `zoneinfo`).
- Pattern converters `%seq` / `%sn` / `%sequenceNumber` (per-event sequence),
  `%sd` / `%structuredData` (RFC 5424 structured data from context), and
  extended throwable options on `%throwable` / `%ex` / `%rEx` / `%xEx`
  (`short`, `nolines`, `depth(N)`).
- Fluent logging API: `logger.atInfo().withMarker(...).withThrowable(...)
  .withContext(k, v).log(msg, *args)` (level captured lazily).
- Pattern converters `%l` / `%location`, `%N` / `%nanos`, `%env{NAME}` (with
  `:-default`), and `%markerSimpleName`; aliases `%processId`, `%threadId`,
  `%hostName`.
- RFC 5424 framing for `SyslogAppender` (`rfc5424=True` with `appName` /
  `procId` / `msgId`).
- `PropertiesRewritePolicy` (`${key}` substitution in the message).
- `onMatch` / `onMismatch` replies (`accept` / `deny` / `neutral`) on the level,
  range, regex, and marker filters.
- `LevelMatchFilter`, `AcceptAllFilter`, `DenyAllFilter`.
- `NullAppender` (discard-all sink).
- Logger level checks: `isTraceEnabled` / `isDebugEnabled` / `isInfoEnabled` /
  `isWarnEnabled` / `isErrorEnabled` / `isFatalEnabled`.
- `%X{key:-default}` and `%K{key:-default}` converters with fallback values.
- Human-readable size strings for `maxBytes` (e.g. `"10MB"`, `"512KB"`).
- `onStartup=True` on rolling appenders to rotate an existing non-empty file on
  first open (`OnStartupTriggeringPolicy`).
- `SMTPAppender`: ring-buffered email alerts on severe events (STARTTLS/SSL,
  auth, pattern subjects).
- `SocketAppender` (TCP) and `SyslogAppender` (RFC 3164 over UDP/TCP) network
  appenders with lazy reconnect and retry throttling.
- `RewriteAppender` with `RewritePolicy` / `MapRewritePolicy` (add/update MDC
  context), configurable via a `policy` key.
- `SizeAndTimeBasedAppender`: rolls on whichever comes first, the size limit or
  the time period; unique indexed rotated-file names.
- PatternLayout selectors `%maxLen` and `%encode` (`HTML`/`XML`/`JSON`/`CRLF`).
- `%c{1.}` logger-name abbreviation and the `%K{key}` map/context converter.
- Composite filters: `AndFilter`, `OrFilter`, `NotFilter` (nestable, buildable
  from config via `filters` / `filter` keys); `Appender.getFilters()`.
- PatternLayout selectors `%replace`, `%equals`, `%equalsIgnoreCase`,
  `%notEmpty` (aliases `%variablesNotEmpty`, `%varsNotEmpty`) with brace-aware,
  nestable option parsing.
- ANSI colour converters `%style`, `%highlight`, and colour shorthand
  (`%red{...}`, `%green{...}`, ...).
- Markers (`Marker`, `getMarker`, `getMarkerNames`) with optional hierarchy,
  a `marker=` keyword on every logging method, the `%marker` pattern converter,
  and `MarkerFilter`.
- PatternLayout converters: `%pid`, `%T`/`%tid`, `%marker`, `%stack`,
  `%throwable`/`%ex`/`%exception`.
- Layouts: `LogfmtLayout`, `XMLLayout`, `HTMLLayout` (with header/footer emitted
  by stream appenders).
- `stack_info=True` on logging calls, captured at the call site and rendered via
  `%stack`; JSON output includes a `stack` field.
- Config variable substitution (`${env:NAME}`, `${env:NAME:-default}`,
  `${sys:attr}`) plus `"substitute": False` to opt out.
- `py.typed` marker and package data.
- Tooling: ruff and coverage configuration, GitHub Actions CI, MIT LICENSE.

### Fixed

- `%msg` is now recognised (previously the trailing `sg` leaked as literal text).

### Changed

- `LogRecord.getExceptionText` now returns a manually assigned `exc_text` even
  when `exc_info` is absent.

## [0.1.0] - 2026-10-11

### Added

- Initial release: logger hierarchy, `Level` registry, `LogRecord`, MDC/NDC,
  `PatternLayout`/`SimpleLayout`/`JSONLayout`, filters (`ThresholdFilter`,
  `LevelRangeFilter`, `RegexFilter`), appenders (`ConsoleAppender`,
  `FileAppender`, `RotatingFileAppender`, `TimedRotatingFileAppender`,
  `AsyncAppender`), error handlers (`ErrorHandler`, `FallbackErrorHandler`),
  stdlib `logging` interop, and dict/YAML configuration.
