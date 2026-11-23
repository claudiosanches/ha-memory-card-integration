# Memory Card integration for Home Assistant

[![GitHub Release][releases-shield]][releases]
![Project Stage][project-stage-shield]
[![License][license-shield]](LICENSE)

[![GitHub Actions][github-actions-shield]][github-actions]
![Project Maintenance][maintenance-shield]

Brings the sensors and the Roll a pick button of the
[Memory Card app](https://github.com/claudiosanches/ha-memory-card) into Home
Assistant without an MQTT broker. Memory Card tracks a video game collection
across consoles.

The app does all the work. This integration reads what it sends, so the
entities match the ones the app's MQTT mode creates, IDs included.

## Requirements

- Home Assistant 2026.3 or newer, with the Memory Card app 0.1.0 or newer.
- The Marketplace, built into Home Assistant since 2026.11, or
  [HACS](https://hacs.xyz) on older versions.

## Installation

[![Open your Home Assistant instance and open a repository in the Marketplace.][marketplace-shield]][marketplace]

1. Select the button above to add this repository to the Marketplace as a
   custom repository, which needs the Marketplace connected to GitHub. On
   Home Assistant before 2026.11, the button adds it to HACS. Download
   **Memory Card** and restart Home Assistant.
2. In the Memory Card app's **Configuration** tab, set **Home Assistant
   sensors** to `integration`, save, and restart the app.
3. Under **Settings > Devices & services**, Memory Card shows as discovered.
   Select **Add**.

There is nothing to type: the app tells Home Assistant where to find it and
which token to use. Setting the option back to `mqtt` or `off` removes the
integration's entry and entities on the app's next start.

## Entities

| Entity | State |
|---|---|
| `sensor.memory_card_games` | Games with at least one owned copy |
| `sensor.memory_card_copies` | Owned copies |
| `sensor.memory_card_wishlist` | Copies on the wishlist |
| `sensor.memory_card_backlog` | Owned games in a status that counts as backlog |
| `sensor.memory_card_playing` | Owned games in a status that counts as playing |
| `sensor.memory_card_last_played` | Title of the game with the latest play session |
| `sensor.memory_card_last_added` | Title of the game whose owned copy was added last |
| `sensor.memory_card_pick` | Title of the latest random pick |
| `button.memory_card_roll_pick` | Picks a random owned game from the backlog |

The app's documentation lists their attributes. Values update about a second
after each change, and the entities are unavailable while the app is stopped.

## Action

`memory_card.roll_pick` picks a random owned game. Without fields it picks
from the backlog, like the button. The fields narrow it down:

```yaml
action: memory_card.roll_pick
data:
  device: switch
  min_local_players: 2
response_variable: pick
```

`play_status`, `platform`, `device`, `genre` and `game_mode` take one slug or
a list of them, as the app's forms show them. `min_local_players` is a
number. The response holds the picked game's `title` and `platforms`.

Like **Pick for me** in the app, the button and the action roll only once the
app has managers. A person pressing or calling them must be one of those
managers; an automation needs nothing more.

## Support

Questions and bugs go to
[GitHub issues](https://github.com/claudiosanches/ha-memory-card-integration/issues).
To support development, use [GitHub Sponsors](https://github.com/sponsors/claudiosanches)
or [Ko-fi](https://ko-fi.com/claudiosanches).

## License

GNU General Public License, version 3 or (at your option) any later version,
like the app. See [LICENSE](LICENSE).

[releases-shield]: https://img.shields.io/github/v/release/claudiosanches/ha-memory-card-integration.svg
[releases]: https://github.com/claudiosanches/ha-memory-card-integration/releases
[project-stage-shield]: https://img.shields.io/badge/project%20stage-production%20ready-brightgreen.svg
[license-shield]: https://img.shields.io/github/license/claudiosanches/ha-memory-card-integration.svg
[github-actions-shield]: https://github.com/claudiosanches/ha-memory-card-integration/actions/workflows/ci.yml/badge.svg
[github-actions]: https://github.com/claudiosanches/ha-memory-card-integration/actions/workflows/ci.yml
[maintenance-shield]: https://img.shields.io/maintenance/yes/2026.svg
[marketplace-shield]: https://my.home-assistant.io/badges/marketplace_repository.svg
[marketplace]: https://my.home-assistant.io/redirect/marketplace_repository/?owner=claudiosanches&repository=ha-memory-card-integration&category=integration
