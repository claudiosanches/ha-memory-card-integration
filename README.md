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

- Home Assistant 2026.11 or newer.
- The Memory Card app 0.1.0 or newer. The button below adds its repository to
  Home Assistant, where you install and start it.

  [![Open your Home Assistant instance and show the add app repository dialog with a specific repository URL pre-filled.][app-shield]][app]

## Installation

[![Open your Home Assistant instance and open a repository in the Marketplace.][marketplace-shield]][marketplace]

1. Select the button above to add this repository to the Marketplace as a
   custom repository, which needs the Marketplace connected to GitHub.
   Download **Memory Card** and restart Home Assistant.
2. In the Memory Card app's **Configuration** tab, set **Home Assistant
   sensors** to `integration`, save, and restart the app.
3. Under **Settings > Devices & services**, Memory Card shows as discovered.
   Select **Add**.

There is nothing to type: the app tells Home Assistant where to find it and
which token to use. Setting the option back to `mqtt` or `off` removes the
integration's entry and entities on the app's next start.

## Entities

The household's:

| Entity | State |
|---|---|
| `sensor.memory_card_games` | Games with at least one owned copy |
| `sensor.memory_card_copies` | Owned copies |
| `sensor.memory_card_wishlist` | Copies on the wishlist |
| `sensor.memory_card_playing` | Owned games someone is playing |
| `sensor.memory_card_last_added` | Title of the game whose owned copy was added last |
| `sensor.memory_card_pick` | Title of the latest random pick, with whose it is |
| `button.memory_card_roll_pick` | Picks a random owned game from the presser's backlog |

Each person who keeps play in Memory Card, up to 16, also gets their own,
named after them, such as `sensor.memory_card_ana_backlog`:

| Entity | State |
|---|---|
| `sensor.memory_card_<name>_backlog` | Their owned games in a status that counts as backlog |
| `sensor.memory_card_<name>_playing` | Their owned games in a status that counts as playing |
| `sensor.memory_card_<name>_last_played` | Title of the game they last played |

[The app's guide](https://github.com/claudiosanches/ha-memory-card/blob/main/docs/sensors.md)
lists their attributes. Values update about a second after each change, and
the entities are unavailable while the app is stopped.

## Action

`memory_card.roll_pick` picks a random owned game from one person's backlog.
Called by a person, it rolls for them; an automation names whose backlog with
`person`. The other fields narrow it down:

```yaml
action: memory_card.roll_pick
data:
  person: person.ana
  device: switch
  min_local_players: 2
response_variable: pick
```

`play_status`, `platform`, `device`, `genre` and `game_mode` take one slug or
a list of up to 10, as the app's forms show them. `min_local_players` is a
number. The response holds the picked game's `title` and `platforms`.

Like **Pick for me** in the app, a roll needs the app to have managers, and
the person to be one of them or a viewer the app lets keep play. A person
rolls only for themselves.

## More

[Memory Card integration](https://github.com/claudiosanches/ha-memory-card/blob/main/docs/integration.md)
in the app's guide compares it with MQTT, and has dashboard and automation
examples, what each error means, and how to troubleshoot and remove it.

## Support

Questions and bugs go to
[GitHub issues](https://github.com/claudiosanches/ha-memory-card-integration/issues).
To support development, use [GitHub Sponsors](https://github.com/sponsors/claudiosanches)
or [Ko-fi](https://ko-fi.com/claudiosanches).

## License

Apache License, version 2.0, like the app and Home Assistant. See
[LICENSE](LICENSE).

[releases-shield]: https://img.shields.io/github/v/release/claudiosanches/ha-memory-card-integration.svg
[releases]: https://github.com/claudiosanches/ha-memory-card-integration/releases
[project-stage-shield]: https://img.shields.io/badge/project%20stage-production%20ready-brightgreen.svg
[license-shield]: https://img.shields.io/github/license/claudiosanches/ha-memory-card-integration.svg
[github-actions-shield]: https://github.com/claudiosanches/ha-memory-card-integration/actions/workflows/ci.yml/badge.svg
[github-actions]: https://github.com/claudiosanches/ha-memory-card-integration/actions/workflows/ci.yml
[maintenance-shield]: https://img.shields.io/maintenance/yes/2026.svg
[app-shield]: https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg
[app]: https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fclaudiosanches%2Fha-memory-card
[marketplace-shield]: https://my.home-assistant.io/badges/marketplace_repository.svg
[marketplace]: https://my.home-assistant.io/redirect/marketplace_repository/?owner=claudiosanches&repository=ha-memory-card-integration&category=integration
