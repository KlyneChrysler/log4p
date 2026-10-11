# Changelog

All notable changes to log4p are documented here. This project follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

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
