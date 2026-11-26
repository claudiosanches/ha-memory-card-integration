# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

First release.

### Added

- Setup from the Memory Card app's discovery, with nothing to type.
- The household's sensors: games, copies, wishlist, playing, last added and
  the latest pick.
- Sensors for each person who keeps play, up to 16: backlog, playing and last
  played.
- The same entities and IDs as the app's MQTT mode, so history carries over.
- **Roll a pick** button, rolling from the backlog of whoever presses it.
- `memory_card.roll_pick` action, for whoever calls it or the person an
  automation names, with filters, answering with the picked game.
- Diagnostics without the token, anyone's play or user IDs.
- English, Spanish and Brazilian Portuguese.

[Unreleased]: https://github.com/claudiosanches/ha-memory-card-integration/commits/main
