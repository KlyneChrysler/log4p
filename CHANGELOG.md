# Changelog

All notable changes to log4p are documented here. This project follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

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
