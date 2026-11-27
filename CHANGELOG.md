# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- The README installs Memory Card by searching the Marketplace, where it is
  listed now, and keeps the button for a Marketplace that does not list it yet.
- The `roll_pick` platform description and README note that slugs are shown
  in the app's forms when `show_slugs` is turned on.

## [0.1.0] - 2026-11-27

First release.

### Added

- Setup from the Memory Card app's discovery, with nothing to type.
- The household's sensors: games, copies, wishlist, playing, last added and
  the latest pick.
- Sensors for each person who keeps play, up to 16: backlog, playing and last
  played.
- The same sensors and IDs as the app's MQTT mode, so history carries over.
- **Roll a pick** button, rolling from the backlog of whoever presses it.
- `memory_card.roll_pick` action, for whoever calls it or the person an
  automation names, with filters including hours to beat, answering with the
  picked game.
- Diagnostics without the token, anyone's play or user IDs.
- English, Spanish and Brazilian Portuguese.

[Unreleased]: https://github.com/claudiosanches/ha-memory-card-integration/compare/v0.1.0...main
[0.1.0]: https://github.com/claudiosanches/ha-memory-card-integration/releases/tag/v0.1.0
